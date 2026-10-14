"""Lot 1, block 1b: public anonymous vote and export 2 (ballots without segments)."""

from __future__ import annotations

import asyncio
import csv
import io
import re
from collections import Counter
from typing import Any

import httpx
import pytest
from bson import ObjectId

from tests.api_support import Api

pytestmark = pytest.mark.integration


async def _open(api: Api, items: int = 3, title: str = "Climat social") -> dict[str, Any]:
    """An open evaluation; returns {headers, evaluation, version_id, slug, item_ids}."""
    headers = await api.headers()
    evaluation, content = await api.new_evaluation(headers, title=title, items=items)
    version_id = content["version"]["id"]
    opened = await api.client.post(
        f"/api/versions/{version_id}/transitions", json={"action": "open"}, headers=headers
    )
    assert opened.status_code == 200, opened.text
    return {
        "headers": headers,
        "evaluation": evaluation,
        "version_id": version_id,
        "slug": evaluation["slug"],
        "item_ids": [i["id"] for g in content["groups"] for i in g["items"]],
    }


def _votes(item_ids: list[str], colors: str = "++,+,~", comment: str | None = None) -> list[Any]:
    keys = colors.split(",")
    votes: list[dict[str, Any]] = [
        {"item_id": item, "color_key": key} for item, key in zip(item_ids, keys, strict=False)
    ]
    if comment is not None:
        votes[0]["comment"] = comment
    return votes


async def _vote(
    api: Api, setup: dict[str, Any], votes: list[Any] | None = None, **headers: str
) -> httpx.Response:
    # A fresh client per voter: no cookie shared between "devices".
    async with httpx.AsyncClient(
        transport=api.client._transport, base_url=api.client.base_url
    ) as c:
        return await c.post(
            f"/api/public/v/{setup['slug']}/ballots",
            json={
                "version_id": setup["version_id"],
                "votes": votes if votes is not None else _votes(setup["item_ids"]),
            },
            headers=headers,
        )


async def _act(api: Api, setup: dict[str, Any], action: str) -> httpx.Response:
    return await api.client.post(
        f"/api/versions/{setup['version_id']}/transitions",
        json={"action": action},
        headers=setup["headers"],
    )


async def _ballot_count(api: Api, version_id: str) -> int:
    version = await api.app.state.database["versions"].find_one({"_id": ObjectId(version_id)})
    return int(version["ballot_count"])


# ── Public page ──────────────────────────────────────────────────────────────


async def test_public_page_shows_the_open_version_and_nothing_about_the_tenant(api: Api) -> None:
    setup = await _open(api)
    response = await api.client.get(f"/api/public/v/{setup['slug']}")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "title",
        "status",
        "version_id",
        "already_voted",
        "intro_md",
        "outro_md",
        "show_vote_example",
        "scale",
        "groups",
    }
    assert (body["status"], body["version_id"], body["already_voted"]) == (
        "open",
        setup["version_id"],
        False,
    )
    assert [s["key"] for s in body["scale"]] == ["++", "+", "~", "-", "--"]
    assert [i["id"] for g in body["groups"] for i in g["items"]] == setup["item_ids"]
    assert api.organization.id not in response.text
    assert api.organization.slug not in response.text


async def test_public_page_of_a_closed_or_unknown_evaluation(api: Api) -> None:
    setup = await _open(api)
    await _act(api, setup, "close")
    closed = (await api.client.get(f"/api/public/v/{setup['slug']}")).json()
    assert (closed["status"], closed["version_id"], closed["groups"]) == ("closed", None, [])
    assert (await api.client.get("/api/public/v/inconnu123")).status_code == 404

    await api.app.state.database["organizations"].update_one(
        {"_id": ObjectId(api.organization.id)}, {"$set": {"status": "suspended"}}
    )
    assert (await api.client.get(f"/api/public/v/{setup['slug']}")).status_code == 404


# ── Writing a ballot ─────────────────────────────────────────────────────────


async def test_a_ballot_stores_no_identity_no_time_and_returns_no_id(api: Api) -> None:
    setup = await _open(api)
    response = await _vote(api, setup, _votes(setup["item_ids"], "++,-"), **{"User-Agent": "X"})
    assert response.status_code == 201, response.text
    assert response.json() == {"status": "recorded"}
    cookie = response.headers["set-cookie"]
    assert cookie.startswith(f"abq_v_{setup['version_id']}=")
    assert "HttpOnly" in cookie
    assert f"Path=/api/public/v/{setup['slug']}" in cookie
    assert "samesite=lax" in cookie.lower()

    database = api.app.state.database
    [ballot] = [b async for b in database["ballots"].find()]
    assert set(ballot) == {
        "_id",
        "organization_id",
        "version_id",
        "submitted_on",
        "groups",
        "rand_key",
    }
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", ballot["submitted_on"])
    assert ballot["groups"] == []
    votes = [v async for v in database["votes"].find()]
    assert {frozenset(v) for v in votes} == {
        frozenset(
            {
                "_id",
                "organization_id",
                "ballot_id",
                "item_id",
                "color_key",
                "comment",
                "comment_status",
            }
        )
    }
    assert sorted(v["color_key"] for v in votes) == ["++", "-"]
    assert await _ballot_count(api, setup["version_id"]) == 1
    organization = await database["organizations"].find_one({"_id": ObjectId(api.organization.id)})
    assert sum(m.get("ballots", 0) for m in organization["usage"].values()) == 1


async def test_ballots_sent_at_different_times_have_identical_metadata(api: Api) -> None:
    setup = await _open(api)
    for _ in range(2):
        assert (await _vote(api, setup)).status_code == 201
    first, second = [b async for b in api.app.state.database["ballots"].find()]
    for key in ("_id", "rand_key"):
        first.pop(key), second.pop(key)
    assert first == second


async def test_the_voted_cookie_blocks_a_second_vote_from_the_same_browser(api: Api) -> None:
    setup = await _open(api)
    first = await _vote(api, setup)
    name, value = first.headers["set-cookie"].split(";", 1)[0].split("=", 1)
    again = await _vote(api, setup, Cookie=f"{name}={value}")
    assert again.status_code == 409
    assert again.json()["error"] == {
        "code": "ALREADY_VOTED",
        "message": "Votre vote a déjà été enregistré.",
    }
    page = await api.client.get(f"/api/public/v/{setup['slug']}", headers={"Cookie": f"{name}=x"})
    assert page.json()["already_voted"] is True
    assert await _ballot_count(api, setup["version_id"]) == 1


async def test_comments_with_identifying_data_are_flagged(api: Api) -> None:
    setup = await _open(api)
    await _vote(api, setup, _votes(setup["item_ids"], "+", "Voir avec Jean Dupont"))
    await _vote(api, setup, _votes(setup["item_ids"], "+", "  Charge trop lourde.  "))
    await _vote(api, setup, _votes(setup["item_ids"], "+", "   "))
    comments = sorted(
        [
            (v["comment"] or "", v["comment_status"])
            async for v in api.app.state.database["votes"].find()
        ]
    )
    assert comments == [
        ("", "published"),
        ("Charge trop lourde.", "published"),
        ("Voir avec Jean Dupont", "flagged"),
    ]


@pytest.mark.parametrize(
    ("votes", "status", "code"),
    [
        ([], 400, "EMPTY_BALLOT"),
        ("duplicate", 400, "DUPLICATE_ITEM"),
        ([{"item_id": "nope", "color_key": "+"}], 409, "CONTENT_CHANGED"),
        ([{"item_id": str(ObjectId()), "color_key": "+"}], 409, "CONTENT_CHANGED"),
        ([{"item_id": "x", "color_key": "+++"}], 422, None),
        ([{"item_id": "x", "color_key": "+", "comment": "x" * 2001}], 422, None),
        ([{"item_id": "x", "color_key": "+", "participant_id": "p"}], 422, None),
    ],
)
async def test_invalid_ballots_are_refused_and_nothing_is_written(
    api: Api, votes: Any, status: int, code: str | None
) -> None:
    setup = await _open(api)
    if votes == "duplicate":
        votes = [{"item_id": setup["item_ids"][0], "color_key": "+"}] * 2
    response = await _vote(api, setup, votes)
    assert response.status_code == status, response.text
    if code:
        assert response.json()["error"]["code"] == code
    assert await _ballot_count(api, setup["version_id"]) == 0
    assert await api.app.state.database["ballots"].count_documents({}) == 0


async def test_a_vote_after_closing_is_refused(api: Api) -> None:
    setup = await _open(api)
    await _act(api, setup, "close")
    response = await _vote(api, setup)
    assert response.status_code == 409
    assert response.json()["error"] == {
        "code": "VERSION_CLOSED",
        "message": "Cette consultation est close, votre réponse n'a pas été enregistrée.",
    }
    # A draft prepared for V1 is refused even once V2 is open (same public link).
    copy = await api.client.post(
        f"/api/versions/{setup['version_id']}/duplicate", headers=setup["headers"]
    )
    await api.client.post(
        f"/api/versions/{copy.json()['id']}/transitions",
        json={"action": "open"},
        headers=setup["headers"],
    )
    assert (await _vote(api, setup)).json()["error"]["code"] == "VERSION_CLOSED"
    assert await api.app.state.database["ballots"].count_documents({}) == 0


async def test_a_foreign_origin_is_refused(api: Api) -> None:
    setup = await _open(api)
    foreign = await _vote(api, setup, Origin="https://evil.example")
    assert foreign.status_code == 403
    assert foreign.json()["error"]["code"] == "ORIGIN_REFUSED"
    same_host = await _vote(api, setup, Origin="http://abaque.test")
    assert same_host.status_code == 201
    configured = await _vote(api, setup, Origin=api.settings.APP_BASE_URL)
    assert configured.status_code == 201


async def test_rate_limit_per_hashed_ip_is_forgotten_at_closing(
    api: Api, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.services.vote.VOTES_PER_IP_PER_HOUR", 2)
    setup = await _open(api)
    assert [(await _vote(api, setup)).status_code for _ in range(3)] == [201, 201, 429]
    limiter = api.app.state.rate_limiter
    keys = [k for k in limiter._hits if k.startswith(f"vote:{setup['version_id']}:")]
    assert len(keys) == 1
    assert "203.0.113.7" not in keys[0]  # hashed, never the raw address
    await _act(api, setup, "close")
    assert not [k for k in limiter._hits if k.startswith(f"vote:{setup['version_id']}:")]


# ── Concurrency (MongoDB replica set) ────────────────────────────────────────


async def test_quota_is_exact_under_concurrent_votes(api: Api) -> None:
    await api.set_entitlements(api.organization.id, max_ballots_per_version=5)
    setup = await _open(api)
    responses = await asyncio.gather(*(_vote(api, setup) for _ in range(10)))
    assert Counter(r.status_code for r in responses) == {201: 5, 403: 5}
    assert {r.json()["error"]["code"] for r in responses if r.status_code == 403} == {
        "LIMIT_REACHED"
    }
    assert await api.app.state.database["ballots"].count_documents({}) == 5
    assert await _ballot_count(api, setup["version_id"]) == 5


async def test_closing_during_votes_never_leaves_a_ballot_after_the_close(api: Api) -> None:
    await api.set_entitlements(api.organization.id, max_ballots_per_version=10_000)
    setup = await _open(api)
    database = api.app.state.database
    for _ in range(15):
        results = await asyncio.gather(
            _vote(api, setup), _vote(api, setup), _act(api, setup, "close")
        )
        accepted = sum(r.status_code == 201 for r in results[:2])
        refused = sum(r.status_code == 409 for r in results[:2])
        assert accepted + refused == 2
        assert results[2].status_code == 200
        # Every accepted ballot is counted; nothing was written for a refused one.
        ballots = await database["ballots"].count_documents({})
        assert ballots == await _ballot_count(api, setup["version_id"])
        assert (await _act(api, setup, "reopen")).status_code == 200
    total_votes = await database["votes"].count_documents({})
    assert total_votes == 3 * await database["ballots"].count_documents({})


async def test_saving_content_never_races_a_first_ballot(api: Api) -> None:
    database = api.app.state.database
    for attempt in range(8):
        setup = await _open(api, title=f"Course {attempt}")
        save = api.client.put(
            f"/api/versions/{setup['version_id']}/content",
            json={
                "revision": 1,
                "groups": [
                    {"name": "Nouveau", "items": [{"short_name": "N", "statement": "Neuf."}]}
                ],
            },
            headers=setup["headers"],
        )
        saved, voted = await asyncio.gather(save, _vote(api, setup))
        # Either the save wins (the vote then sees new items: CONTENT_CHANGED), or the
        # ballot wins (the content is then locked: CONTENT_LOCKED). Never both.
        assert sorted([saved.status_code, voted.status_code]) in ([200, 409], [201, 409])
        version_oid = ObjectId(setup["version_id"])
        items = {i["_id"] async for i in database["items"].find({"version_id": version_oid})}
        ballots = [b["_id"] async for b in database["ballots"].find({"version_id": version_oid})]
        async for vote in database["votes"].find({"ballot_id": {"$in": ballots}}):
            assert vote["item_id"] in items  # never a vote on a replaced item
        await _act(api, setup, "close")
        await _act(api, setup, "archive")  # frees the trial quota for the next attempt


# ── Export 2 ─────────────────────────────────────────────────────────────────


def _rows(response: httpx.Response) -> list[list[str]]:
    return list(csv.reader(io.StringIO(response.content.decode("utf-8-sig")), delimiter=";"))


async def test_export_is_refused_below_k_and_with_a_filter(api: Api) -> None:
    setup = await _open(api)
    url = f"/api/versions/{setup['version_id']}/exports/ballots.csv"
    for _ in range(2):
        await _vote(api, setup)
    below = await api.client.get(url, headers=setup["headers"])
    assert below.status_code == 409
    assert below.json()["error"]["code"] == "BELOW_THRESHOLD"
    await _vote(api, setup)
    filtered = await api.client.get(url, params={"segment": "x"}, headers=setup["headers"])
    assert filtered.status_code == 400
    assert filtered.json()["error"]["code"] == "FILTER_NOT_ALLOWED"
    assert (await api.client.get(url, headers=setup["headers"])).status_code == 200

    await api.set_entitlements(api.organization.id, csv_export=False)
    refused = await api.client.get(url, headers=setup["headers"])
    assert refused.json()["error"]["code"] == "FEATURE_NOT_ALLOWED"


async def test_export_has_no_date_no_order_and_hides_moderated_comments(api: Api) -> None:
    setup = await _open(api, items=3)
    ids = setup["item_ids"]
    await _vote(api, setup, _votes(ids, "++,-", "Très juste"))
    await _vote(api, setup, _votes(ids, "--", "Parlez-en à Jean Dupont"))
    for colors in ("~,~,~", "+,+,+", "-,-,-", "++,++,++", "--,--,--", "+,~,-"):
        await _vote(api, setup, _votes(ids, colors))
    url = f"/api/versions/{setup['version_id']}/exports/ballots.csv"

    first = await api.client.get(url, headers=setup["headers"])
    assert first.status_code == 200
    assert first.headers["cache-control"] == "no-store"
    disposition = first.headers["content-disposition"]
    assert re.search(r'filename="abaque_[a-z0-9]{10}_V1_ballots\.csv"', disposition)
    assert first.content.startswith(b"\xef\xbb\xbf")
    assert b"\r\n" in first.content
    rows = _rows(first)
    assert rows[0] == [
        "ballot_ref",
        "item_position",
        "item_short_name",
        "color_key",
        "color_label",
        "comment",
    ]
    body = rows[1:]
    assert len(body) == 8 * 3
    text = first.content.decode("utf-8-sig")
    assert not re.search(r"\d{4}-\d{2}-\d{2}", text)  # no date anywhere
    assert setup["version_id"] not in text and api.organization.id not in text

    by_ballot: dict[str, list[list[str]]] = {}
    for row in body:
        by_ballot.setdefault(row[0], []).append(row)
    assert sorted(by_ballot) == [f"B{n:03d}" for n in range(1, 9)]
    for lines in by_ballot.values():
        assert [line[1] for line in lines] == ["1", "2", "3"]  # grouped, by item position
    tails = [r[3:] for r in body]
    assert ["'++", "Tout à fait d'accord", "Très juste"] in tails  # formula-neutralised key
    assert ["", "non exprimé", ""] in tails
    assert ["'--", "Pas du tout d'accord", ""] in tails
    assert "Jean Dupont" not in text  # flagged: excluded until moderated

    # A second generation has the same ballots, but other references and another order.
    second = _rows(await api.client.get(url, headers=setup["headers"]))[1:]

    def ballots(rows: list[list[str]]) -> dict[str, tuple[tuple[str, ...], ...]]:
        grouped: dict[str, list[tuple[str, ...]]] = {}
        for row in rows:
            grouped.setdefault(row[0], []).append(tuple(row[1:]))
        return {ref: tuple(lines) for ref, lines in grouped.items()}

    first_ballots, second_ballots = ballots(body), ballots(second)
    assert sorted(first_ballots.values()) == sorted(second_ballots.values())
    assert first_ballots != second_ballots  # references drawn again (P = 1/8! to fail)
    order = lambda rows: [tuple(r[1:]) for r in rows]  # noqa: E731
    assert order(body) != order(second)  # order drawn again (P = 1/8! to fail)
    events = [e["kind"] async for e in api.app.state.database["version_events"].find()]
    assert events.count("export_ballots") == 2

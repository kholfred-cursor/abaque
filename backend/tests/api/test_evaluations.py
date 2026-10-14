"""Lot 1, block 1a: evaluations, versions, lifecycle, content, items CSV."""

from __future__ import annotations

import asyncio
import re
from typing import Any

import pytest
from bson import ObjectId

from tests.api_support import Api

pytestmark = pytest.mark.integration


async def _content(api: Api, headers: dict[str, str], version_id: str) -> dict[str, Any]:
    response = await api.client.get(f"/api/versions/{version_id}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


async def _act(api: Api, headers: dict[str, str], version_id: str, action: str) -> Any:
    return await api.client.post(
        f"/api/versions/{version_id}/transitions", json={"action": action}, headers=headers
    )


# ── Evaluations ──────────────────────────────────────────────────────────────


async def test_create_gives_a_random_public_slug_and_an_empty_draft(api: Api) -> None:
    headers = await api.headers()
    response = await api.client.post(
        "/api/evaluations", json={"title": "  Climat social  "}, headers=headers
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["title"] == "Climat social"
    assert re.fullmatch(r"[a-km-np-z2-9]{10}", body["slug"])  # no org, no title inside
    assert body["participation_mode"] == "anonymous"
    assert body["anonymity_threshold"] == 3
    [version] = body["versions"]
    assert (version["label"], version["status"], version["ballot_count"]) == ("V1", "draft", 0)

    content = await _content(api, headers, version["id"])
    assert [g["name"] for g in content["groups"]] == ["Général"]
    assert content["groups"][0]["items"] == []
    assert content["version"]["editable"] is True
    assert content["scale"][0]["label"] == "Tout à fait d'accord"

    listed = await api.client.get("/api/evaluations", headers=headers)
    assert [e["id"] for e in listed.json()] == [body["id"]]


async def test_content_routes_require_a_verified_email(api: Api) -> None:
    headers = await api.headers()
    await api.app.state.database["admins"].update_one(
        {"_id": ObjectId(api.owner_id)}, {"$set": {"email_verified": False}}
    )
    response = await api.client.post("/api/evaluations", json={"title": "X"}, headers=headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "EMAIL_NOT_VERIFIED"


async def test_only_the_anonymous_mode_is_available_in_lot_1(api: Api) -> None:
    headers = await api.headers()
    response = await api.client.post(
        "/api/evaluations",
        json={"title": "X", "participation_mode": "auth_open"},
        headers=headers,
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "MODE_NOT_AVAILABLE"


async def test_quota_counts_evaluations_with_a_non_archived_version(api: Api) -> None:
    headers = await api.headers()  # trial plan: 1 active evaluation
    _, content = await api.new_evaluation(headers)
    refused = await api.client.post("/api/evaluations", json={"title": "B"}, headers=headers)
    assert refused.status_code == 403
    assert refused.json()["error"]["code"] == "LIMIT_REACHED"

    assert (await _act(api, headers, content["version"]["id"], "archive")).status_code == 200
    accepted = await api.client.post("/api/evaluations", json={"title": "B"}, headers=headers)
    assert accepted.status_code == 201


async def test_concurrent_creations_never_exceed_the_quota(api: Api) -> None:
    await api.set_entitlements(api.organization.id, max_active_evaluations=2)
    headers = await api.headers()
    responses = await asyncio.gather(
        *(
            api.client.post("/api/evaluations", json={"title": f"E{n}"}, headers=headers)
            for n in range(8)
        )
    )
    assert sorted(r.status_code for r in responses) == [201, 201] + [403] * 6
    count = await api.app.state.database["evaluations"].count_documents({})
    assert count == 2
    organization = await api.app.state.database["organizations"].find_one(
        {"_id": ObjectId(api.organization.id)}
    )
    [month] = organization["usage"].values()
    assert month["evaluations"] == 2  # only committed creations are counted


async def test_update_changes_only_the_fields_sent(api: Api) -> None:
    headers = await api.headers()
    evaluation, _ = await api.new_evaluation(headers)
    url = f"/api/evaluations/{evaluation['id']}"

    response = await api.client.patch(
        url, json={"intro_md": "**Bienvenue**", "anonymity_threshold": 5}, headers=headers
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["title"], body["intro_md"], body["anonymity_threshold"]) == (
        "Climat social",
        "**Bienvenue**",
        5,
    )

    lowered = await api.client.patch(url, json={"anonymity_threshold": 4}, headers=headers)
    assert lowered.json()["error"]["code"] == "THRESHOLD_DECREASE"
    empty_title = await api.client.patch(url, json={"title": None}, headers=headers)
    assert empty_title.status_code == 400
    unknown = await api.client.patch(url, json={"organization_id": "x"}, headers=headers)
    assert unknown.status_code == 422


async def test_unknown_or_malformed_ids_are_404(api: Api) -> None:
    headers = await api.headers()
    for url in ("/api/evaluations/abc", f"/api/evaluations/{ObjectId()}", "/api/versions/abc"):
        response = await api.client.get(url, headers=headers)
        assert response.status_code == 404, url


# ── Content ──────────────────────────────────────────────────────────────────


async def test_content_is_saved_in_order_and_keeps_existing_ids(api: Api) -> None:
    headers = await api.headers()
    _, content = await api.new_evaluation(headers, items=3)
    version_id = content["version"]["id"]
    group = content["groups"][0]
    first, second, third = group["items"]
    assert content["version"]["revision"] == 1

    reordered = {
        "revision": 1,
        "groups": [
            {"name": "Nouveau", "items": [{"short_name": "Neuf", "statement": "Nouvel item."}]},
            {"id": group["id"], "name": "Général", "items": [third, first]},
        ],
        "color_labels": {"++": "  Excellent  ", "-": ""},
    }
    response = await api.client.put(
        f"/api/versions/{version_id}/content", json=reordered, headers=headers
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert [g["name"] for g in body["groups"]] == ["Nouveau", "Général"]
    assert body["groups"][1]["id"] == group["id"]
    assert [i["id"] for i in body["groups"][1]["items"]] == [third["id"], first["id"]]
    assert second["id"] not in str(body)
    assert body["color_labels"] == {"++": "Excellent"}
    assert body["version"]["revision"] == 2

    stale = await api.client.put(
        f"/api/versions/{version_id}/content", json=reordered, headers=headers
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "CONTENT_CONFLICT"


async def test_custom_labels_complete_the_scale(api: Api) -> None:
    headers = await api.headers()
    evaluation, content = await api.new_evaluation(headers)
    await api.client.patch(
        f"/api/evaluations/{evaluation['id']}", json={"vote_preset": "custom"}, headers=headers
    )
    response = await api.client.put(
        f"/api/versions/{content['version']['id']}/content",
        json={
            "revision": 1,
            "groups": content["groups"],
            "color_labels": {"++": "Oui", "--": "Non"},
        },
        headers=headers,
    )
    labels = [entry["label"] for entry in response.json()["scale"]]
    assert labels == [
        "Oui",
        "Plutôt d'accord",
        "Avis partagé, opinion mitigée",
        "Plutôt pas d'accord",
        "Non",
    ]


async def test_content_is_locked_once_a_ballot_exists(api: Api) -> None:
    headers = await api.headers()
    evaluation, content = await api.new_evaluation(headers)
    version_id = content["version"]["id"]
    await api.app.state.database["versions"].update_one(
        {"_id": ObjectId(version_id)}, {"$set": {"ballot_count": 1}}
    )
    response = await api.client.put(
        f"/api/versions/{version_id}/content",
        json={"revision": 1, "groups": []},
        headers=headers,
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONTENT_LOCKED"
    assert (await _content(api, headers, version_id))["version"]["editable"] is False

    preset = await api.client.patch(
        f"/api/evaluations/{evaluation['id']}", json={"vote_preset": "score"}, headers=headers
    )
    assert preset.json()["error"]["code"] == "PRESET_LOCKED"


async def test_content_size_limits(api: Api) -> None:
    headers = await api.headers()
    _, content = await api.new_evaluation(headers)
    too_many = [{"short_name": f"I{n}", "statement": "S"} for n in range(501)]
    response = await api.client.put(
        f"/api/versions/{content['version']['id']}/content",
        json={"revision": 1, "groups": [{"name": "G", "items": too_many}]},
        headers=headers,
    )
    assert response.status_code in (400, 422)
    long_name = await api.client.put(
        f"/api/versions/{content['version']['id']}/content",
        json={
            "revision": 1,
            "groups": [{"name": "G", "items": [{"short_name": "x" * 51, "statement": "S"}]}],
        },
        headers=headers,
    )
    assert long_name.status_code == 422


# ── Lifecycle ────────────────────────────────────────────────────────────────


async def test_lifecycle_is_enforced_and_journaled(api: Api) -> None:
    await api.set_entitlements(api.organization.id, max_active_evaluations=5)
    headers = await api.headers()
    created = await api.client.post("/api/evaluations", json={"title": "X"}, headers=headers)
    empty_version = created.json()["versions"][0]["id"]
    no_items = await _act(api, headers, empty_version, "open")
    assert no_items.json()["error"]["code"] == "NO_ITEMS"

    _, content = await api.new_evaluation(headers)
    version_id = content["version"]["id"]
    assert (await _act(api, headers, version_id, "close")).json()["error"]["code"] == (
        "INVALID_TRANSITION"
    )
    opened = await _act(api, headers, version_id, "open")
    assert opened.json()["status"] == "open"
    assert (await _act(api, headers, version_id, "archive")).status_code == 409

    copy = await api.client.post(f"/api/versions/{version_id}/duplicate", headers=headers)
    assert copy.status_code == 201
    assert (copy.json()["label"], copy.json()["status"]) == ("V2", "draft")
    second_open = await _act(api, headers, copy.json()["id"], "open")
    assert second_open.json()["error"]["code"] == "ANOTHER_VERSION_OPEN"

    for action, status in (("close", "closed"), ("reopen", "open"), ("close", "closed")):
        response = await _act(api, headers, version_id, action)
        assert response.json()["status"] == status, response.text
    assert (await _act(api, headers, copy.json()["id"], "open")).status_code == 200
    assert (await _act(api, headers, version_id, "archive")).json()["status"] == "archived"
    assert (await _act(api, headers, version_id, "reopen")).status_code == 409

    stored = await api.app.state.database["versions"].find_one({"_id": ObjectId(version_id)})
    assert stored["closed_at"] is not None
    assert stored["credential_key_id"] == api.settings.credential_key_id
    events = api.app.state.database["version_events"].find(
        {"version_id": ObjectId(version_id)}, sort=[("at", 1)]
    )
    kinds = [event["kind"] async for event in events]
    assert kinds == ["opened", "closed", "reopened", "closed", "archived"]

    locked = await api.client.put(
        f"/api/versions/{version_id}/content", json={"revision": 1, "groups": []}, headers=headers
    )
    assert locked.json()["error"]["code"] == "CONTENT_LOCKED"


async def test_concurrent_opens_leave_a_single_open_version(api: Api) -> None:
    headers = await api.headers()
    _, content = await api.new_evaluation(headers)
    version_id = content["version"]["id"]
    copies = [
        (await api.client.post(f"/api/versions/{version_id}/duplicate", headers=headers)).json()[
            "id"
        ]
        for _ in range(4)
    ]
    responses = await asyncio.gather(
        *(_act(api, headers, vid, "open") for vid in [version_id, *copies])
    )
    assert sorted(r.status_code for r in responses) == [200, 409, 409, 409, 409]
    count = await api.app.state.database["versions"].count_documents({"status": "open"})
    assert count == 1


# ── Duplicate and delete ─────────────────────────────────────────────────────


async def test_duplicate_copies_texts_and_content_under_a_new_slug(api: Api) -> None:
    await api.set_entitlements(api.organization.id, max_active_evaluations=5)
    headers = await api.headers()
    evaluation, content = await api.new_evaluation(headers)
    await api.client.patch(
        f"/api/evaluations/{evaluation['id']}",
        json={"intro_md": "Intro", "outro_md": "Merci", "show_vote_example": True},
        headers=headers,
    )
    response = await api.client.post(
        f"/api/evaluations/{evaluation['id']}/duplicate", headers=headers
    )
    assert response.status_code == 201, response.text
    copy = response.json()
    assert copy["title"] == "Climat social (copie)"
    assert copy["slug"] != evaluation["slug"]
    assert (copy["intro_md"], copy["outro_md"], copy["show_vote_example"]) == (
        "Intro",
        "Merci",
        True,
    )
    copied = await _content(api, headers, copy["versions"][0]["id"])
    names = [i["short_name"] for g in copied["groups"] for i in g["items"]]
    assert names == ["Item 1", "Item 2"]
    original_ids = {i["id"] for g in content["groups"] for i in g["items"]}
    assert not original_ids & {i["id"] for g in copied["groups"] for i in g["items"]}


async def test_delete_removes_everything_attached(api: Api) -> None:
    headers = await api.headers()
    evaluation, content = await api.new_evaluation(headers)
    version_oid = ObjectId(content["version"]["id"])
    database = api.app.state.database
    org = ObjectId(api.organization.id)
    ballot_id = "0b5a5d0e-4c1b-4f6a-9b1e-2f3a4b5c6d7e"
    item_oid = ObjectId(content["groups"][0]["items"][0]["id"])
    await database["ballots"].insert_one(
        {
            "_id": ballot_id,
            "organization_id": org,
            "version_id": version_oid,
            "submitted_on": "2026-10-13",
            "groups": [],
            "rand_key": 0.5,
        }
    )
    await database["votes"].insert_one(
        {
            "_id": "1c6b6e1f-5d2c-4a7b-8c2f-3a4b5c6d7e8f",
            "organization_id": org,
            "ballot_id": ballot_id,
            "item_id": item_oid,
            "color_key": "+",
            "comment": None,
            "comment_status": "published",
        }
    )
    response = await api.client.delete(f"/api/evaluations/{evaluation['id']}", headers=headers)
    assert response.status_code == 204
    for name in ("evaluations", "versions", "item_groups", "items", "ballots", "votes"):
        assert await database[name].count_documents({}) == 0, name
    gone = await api.client.get(f"/api/evaluations/{evaluation['id']}", headers=headers)
    assert gone.status_code == 404


# ── Items CSV ────────────────────────────────────────────────────────────────


async def test_items_csv_round_trip(api: Api) -> None:
    headers = await api.headers()
    _, content = await api.new_evaluation(headers, items=0)
    version_id = content["version"]["id"]
    source = (
        "﻿groupe;nom_court;affirmation\r\n"
        "Management;Écoute;Mon manager m'écoute.\r\n"
        ";Charge;-La charge de travail est raisonnable\r\n"
        'Management;Clarté;"Les objectifs sont clairs; et partagés."\r\n'
        ";;\r\n"
    )
    imported = await api.client.post(
        f"/api/versions/{version_id}/items/import",
        json={"revision": 1, "csv": source},
        headers=headers,
    )
    assert imported.status_code == 200, imported.text
    groups = imported.json()["groups"]
    assert [(g["name"], [i["short_name"] for i in g["items"]]) for g in groups] == [
        ("Management", ["Écoute", "Clarté"]),
        ("Général", ["Charge"]),
    ]

    exported = await api.client.get(f"/api/versions/{version_id}/items.csv", headers=headers)
    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith("text/csv")
    disposition = exported.headers["content-disposition"]
    assert re.search(r'filename="abaque_[a-z0-9]{10}_V1_items\.csv"', disposition)
    raw = exported.content
    assert raw.startswith("﻿".encode())
    text = raw.decode("utf-8-sig")
    assert text.splitlines()[0] == "group;short_name;statement"
    assert "\r\n" in text
    assert "'-La charge" in text  # formula neutralised

    appended = await api.client.post(
        f"/api/versions/{version_id}/items/import",
        json={"revision": 2, "csv": text, "mode": "append"},
        headers=headers,
    )
    assert appended.status_code == 200, appended.text
    statements = [i["statement"] for g in appended.json()["groups"] for i in g["items"]]
    assert statements.count("-La charge de travail est raisonnable") == 2  # prefix undone


async def test_invalid_items_csv_names_the_line(api: Api) -> None:
    headers = await api.headers()
    _, content = await api.new_evaluation(headers)
    response = await api.client.post(
        f"/api/versions/{content['version']['id']}/items/import",
        json={"revision": 1, "csv": "group;short_name;statement\nG;;Affirmation\n"},
        headers=headers,
    )
    assert response.status_code == 400
    assert response.json()["error"] == {
        "code": "CSV_INVALID",
        "message": "Ligne 2 : nom court (1 à 50 caractères), affirmation (1 à 2000 caractères) "
        "et groupe (200 caractères au plus) sont requis.",
    }

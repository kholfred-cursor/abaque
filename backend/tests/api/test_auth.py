"""Block 5a: login, cookies, CSRF, JWT validation, refresh rotation, logout, isolation."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

import httpx
import jwt
import pytest
from fastapi import Depends

from app.api.deps import require_verified
from app.core.logging import JsonFormatter
from app.core.security import create_access_token, hash_token
from tests.api_support import PASSWORD, Api

pytestmark = pytest.mark.integration


def _set_cookies(response: httpx.Response) -> dict[str, str]:
    """Map cookie name -> raw Set-Cookie header (attributes included)."""
    return {h.split("=", 1)[0]: h for h in response.headers.get_list("set-cookie")}


def _value(raw: str) -> str:
    return raw.split(";", 1)[0].split("=", 1)[1]


async def _logged_in(api: Api) -> dict[str, str]:
    response = await api.login()
    assert response.status_code == 200
    return {name: _value(raw) for name, raw in _set_cookies(response).items()}


async def test_login_sets_three_cookies_with_the_specified_attributes(api: Api) -> None:
    response = await api.login()

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == api.owner_email
    assert body["organization"]["id"] == api.organization.id
    cookies = {k: v.lower() for k, v in _set_cookies(response).items()}
    assert set(cookies) == {"abq_access", "abq_refresh", "abq_csrf"}
    assert "httponly" in cookies["abq_access"]
    assert "samesite=lax" in cookies["abq_access"]
    assert "path=/api" in cookies["abq_access"]
    assert "httponly" in cookies["abq_refresh"]
    assert "samesite=strict" in cookies["abq_refresh"]
    assert "path=/api/auth" in cookies["abq_refresh"]
    assert "httponly" not in cookies["abq_csrf"]
    assert "path=/" in cookies["abq_csrf"]
    assert all("secure" not in raw for raw in cookies.values())  # COOKIE_SECURE=false in tests


async def test_unknown_email_and_wrong_password_are_indistinguishable(api: Api) -> None:
    unknown = await api.login(email="nobody@alpha.example")
    wrong = await api.login(password="Wrong-Password-123")
    malformed = await api.login(email="not an email")

    assert unknown.status_code == wrong.status_code == malformed.status_code == 401
    assert unknown.json() == wrong.json() == malformed.json()
    assert unknown.json()["error"]["code"] == "INVALID_CREDENTIALS"


async def test_login_is_rate_limited_per_account_with_retry_after(api: Api) -> None:
    for _ in range(5):
        assert (await api.login(password="Wrong-Password-123")).status_code == 401

    blocked = await api.login()  # even the right password is refused now
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "RATE_LIMITED"
    assert int(blocked.headers["Retry-After"]) > 0


async def test_login_is_rate_limited_per_ip(api: Api) -> None:
    for i in range(10):
        await api.login(email=f"user{i}@elsewhere.example", password="Wrong-Password-123")
    assert (await api.login()).status_code == 429


def _forge(api: Api, **changes: Any) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "iss": "abaque",
        "aud": "abaque-admin",
        "sub": api.owner_id,
        "organization_id": api.organization.id,
        "role": "owner",
        "iat": now,
        "exp": now + timedelta(minutes=5),
        "jti": "x",
    }
    key = changes.pop("_key", api.settings.JWT_SECRET.get_secret_value())
    algorithm = changes.pop("_alg", "HS256")
    payload.update(changes)
    return jwt.encode(payload, key, algorithm=algorithm)


@pytest.mark.parametrize(
    "case",
    ["expired", "alg_none", "bad_signature", "bad_audience", "bad_issuer", "unknown_subject"],
)
async def test_invalid_access_tokens_get_401(api: Api, case: str) -> None:
    token = {
        "expired": lambda: _forge(api, exp=datetime(2020, 1, 1, tzinfo=UTC)),
        "alg_none": lambda: _forge(api, _alg="none", _key=None),
        "bad_signature": lambda: _forge(api, _key="k" * 32),
        "bad_audience": lambda: _forge(api, aud="someone-else"),
        "bad_issuer": lambda: _forge(api, iss="someone-else"),
        "unknown_subject": lambda: _forge(api, sub="0123456789abcdef01234567"),
    }[case]()
    response = await api.client.get("/api/auth/me", headers=api.cookie_header(abq_access=token))
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "NOT_AUTHENTICATED"


async def test_me_without_cookie_is_401(api: Api) -> None:
    assert (await api.client.get("/api/auth/me")).status_code == 401


@pytest.mark.parametrize("header", [None, "", "wrong-token"])
async def test_state_changing_requests_require_matching_csrf(api: Api, header: str | None) -> None:
    cookies = await _logged_in(api)
    headers = api.cookie_header(abq_refresh=cookies["abq_refresh"], abq_csrf=cookies["abq_csrf"])
    if header is not None:
        headers["X-CSRF-Token"] = header
    response = await api.client.post("/api/auth/logout", headers=headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CSRF_FAILED"


async def _refresh(api: Api, cookies: dict[str, str]) -> httpx.Response:
    headers = api.cookie_header(abq_refresh=cookies["abq_refresh"], abq_csrf=cookies["abq_csrf"])
    headers["X-CSRF-Token"] = cookies["abq_csrf"]
    return await api.client.post("/api/auth/refresh", headers=headers)


async def test_refresh_rotates_all_three_cookies(api: Api) -> None:
    cookies = await _logged_in(api)
    response = await _refresh(api, cookies)

    assert response.status_code == 204
    rotated = {k: _value(v) for k, v in _set_cookies(response).items()}
    assert rotated["abq_refresh"] != cookies["abq_refresh"]
    assert rotated["abq_csrf"] != cookies["abq_csrf"]
    me = await api.client.get(
        "/api/auth/me", headers=api.cookie_header(abq_access=rotated["abq_access"])
    )
    assert me.status_code == 200


async def test_two_tabs_refreshing_at_once_do_not_log_out(api: Api) -> None:
    cookies = await _logged_in(api)
    first, second = await asyncio.gather(_refresh(api, cookies), _refresh(api, cookies))

    assert sorted([first.status_code, second.status_code]) == [204, 409]
    loser = first if first.status_code == 409 else second
    winner = second if loser is first else first
    assert loser.json()["error"]["code"] == "SESSION_ROTATED"
    assert "set-cookie" not in loser.headers  # cookies untouched for the losing tab
    rotated = {k: _value(v) for k, v in _set_cookies(winner).items()}
    assert (await _refresh(api, rotated)).status_code == 204  # winner's session still alive


async def test_replay_after_grace_window_revokes_everything(api: Api) -> None:
    cookies = await _logged_in(api)
    other_device = await _logged_in(api)
    assert (await _refresh(api, cookies)).status_code == 204
    await api.app.state.database["admin_sessions"].update_one(
        {"token_hash": hash_token(cookies["abq_refresh"])},
        {"$set": {"consumed_at": datetime.now(UTC) - timedelta(minutes=1)}},
    )

    replay = await _refresh(api, cookies)

    assert replay.status_code == 401
    assert replay.json()["error"]["code"] == "SESSION_REVOKED"
    assert "abq_refresh" in _set_cookies(replay)  # cookies cleared
    assert (await _refresh(api, other_device)).status_code == 401  # all sessions revoked


async def test_logout_revokes_the_session_and_clears_cookies(api: Api) -> None:
    cookies = await _logged_in(api)
    headers = api.cookie_header(abq_refresh=cookies["abq_refresh"], abq_csrf=cookies["abq_csrf"])
    headers["X-CSRF-Token"] = cookies["abq_csrf"]

    response = await api.client.post("/api/auth/logout", headers=headers)

    assert response.status_code == 204
    assert set(_set_cookies(response)) == {"abq_access", "abq_refresh", "abq_csrf"}
    assert (await _refresh(api, cookies)).status_code == 401


async def test_organization_route_never_leaks_another_tenant(api: Api) -> None:
    other, _ = await api.add_tenant("beta")
    cookies = await _logged_in(api)
    headers = api.cookie_header(abq_access=cookies["abq_access"])

    response = await api.client.get(
        "/api/organization", params={"organization_id": other.id}, headers=headers
    )

    assert response.status_code == 200
    assert response.json()["id"] == api.organization.id
    assert response.json()["entitlements"]["max_active_evaluations"] == 1


async def test_superadmin_is_refused_on_organization_routes(api: Api) -> None:
    token = create_access_token(api.settings, sub=api.owner_id, organization_id=None, role="owner")
    await api.app.state.database["admins"].update_one(
        {"email": api.owner_email}, {"$set": {"organization_id": None, "role": "superadmin"}}
    )
    response = await api.client.get(
        "/api/organization", headers=api.cookie_header(abq_access=token)
    )
    assert response.status_code == 403


async def test_require_verified_blocks_unverified_accounts(api: Api) -> None:
    @api.app.get("/api/_test/business")
    async def business(_: Annotated[Any, Depends(require_verified)]) -> dict[str, bool]:
        return {"ok": True}

    cookies = await _logged_in(api)
    headers = api.cookie_header(abq_access=cookies["abq_access"])
    assert (await api.client.get("/api/_test/business", headers=headers)).status_code == 200

    await api.app.state.database["admins"].update_one(
        {"email": api.owner_email}, {"$set": {"email_verified": False}}
    )
    blocked = await api.client.get("/api/_test/business", headers=headers)
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "EMAIL_NOT_VERIFIED"


async def test_full_flow_leaves_no_secret_in_logs(
    api: Api, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    await api.login(password="Wrong-Password-123")
    cookies = await _logged_in(api)
    await _refresh(api, cookies)

    formatter = JsonFormatter()
    output = "\n".join(formatter.format(record) for record in caplog.records)
    for secret in (PASSWORD, "Wrong-Password-123", api.owner_email, *cookies.values()):
        assert secret not in output
    assert all(json.loads(line) for line in output.splitlines() if line)


async def test_every_route_documents_its_error_responses(api: Api) -> None:
    schema = api.app.openapi()
    for path, methods in schema["paths"].items():
        if not path.startswith("/api/") or path.startswith("/api/_test"):
            continue
        for operation in methods.values():
            documented = {code for code in operation["responses"] if code.startswith(("4", "5"))}
            assert documented, f"{path} documents no error response"

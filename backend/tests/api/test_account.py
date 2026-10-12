"""Block 5b: signup, email verification, password forgot/reset/change, sessions."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.core.security import hash_token
from tests.api_support import PASSWORD, Api

pytestmark = pytest.mark.integration
NEW_PASSWORD = "Another-Strong-Pass-77"
FIREFOX = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0"


def _cookies(response: httpx.Response) -> dict[str, str]:
    return {
        h.split("=", 1)[0]: h.split(";", 1)[0].split("=", 1)[1]
        for h in response.headers.get_list("set-cookie")
    }


async def _login(
    api: Api, email: str | None = None, password: str = PASSWORD, ua: str = FIREFOX
) -> dict[str, str]:
    response = await api.client.post(
        "/api/auth/login",
        json={"email": email or api.owner_email, "password": password},
        headers={"User-Agent": ua},
    )
    assert response.status_code == 200, response.text
    return _cookies(response)


def _auth(api: Api, cookies: dict[str, str], csrf: bool = True) -> dict[str, str]:
    headers = api.cookie_header(**cookies)
    if csrf:
        headers["X-CSRF-Token"] = cookies["abq_csrf"]
    return headers


async def _signup(api: Api, email: str, password: str = PASSWORD) -> httpx.Response:
    return await api.client.post(
        "/api/auth/signup",
        json={"organization_name": "Cabinet Dupré & Fils", "email": email, "password": password},
    )


# ── Signup & email verification ──


async def test_signup_creates_trial_organization_unverified_owner_and_sends_link(api: Api) -> None:
    response = await _signup(api, "Nouvelle@Example.com")

    assert response.status_code == 202
    to, template, _ = api.mailer.sent[-1]
    assert (to, template) == ("nouvelle@example.com", "verify_email")
    owner = await api.app.state.store.admin_auth().find_by_email("nouvelle@example.com")
    assert owner is not None
    assert owner.email_verified is False
    assert owner.role == "owner"
    org = await api.app.state.database["organizations"].find_one({"name": "Cabinet Dupré & Fils"})
    assert org is not None
    assert org["plan_code"] == "trial"
    assert org["slug"].startswith("cabinet-dupre-fils-")


async def test_signup_with_an_existing_email_looks_identical_and_warns_the_owner(api: Api) -> None:
    fresh = await _signup(api, "fresh@example.com")
    existing = await _signup(api, api.owner_email)

    assert fresh.status_code == existing.status_code == 202
    assert fresh.content == existing.content
    assert api.mailer.sent[-1][:2] == (api.owner_email, "account_exists")
    assert await api.app.state.database["organizations"].count_documents({}) == 2  # alpha + fresh


@pytest.mark.parametrize(
    "password", ["short", "fresh@example.com", "password1234"], ids=["short", "email", "common"]
)
async def test_signup_enforces_password_policy(api: Api, password: str) -> None:
    response = await _signup(api, "fresh@example.com", password)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "PASSWORD_POLICY"
    assert await api.app.state.store.admin_auth().find_by_email("fresh@example.com") is None


async def test_signup_can_be_disabled(api: Api) -> None:
    api.app.state.settings = api.settings.model_copy(update={"SIGNUP_ENABLED": False})
    response = await _signup(api, "fresh@example.com")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "SIGNUP_DISABLED"


async def test_signup_is_rate_limited_per_ip(api: Api) -> None:
    for i in range(5):
        assert (await _signup(api, f"user{i}@example.com")).status_code == 202
    blocked = await _signup(api, "user6@example.com")
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers


async def test_email_verification_link_works_once(api: Api) -> None:
    await _signup(api, "fresh@example.com")
    token = api.mailer.last_token("verify_email")

    first = await api.client.post("/api/auth/verify-email", json={"token": token})
    second = await api.client.post("/api/auth/verify-email", json={"token": token})

    assert first.status_code == 204  # no CSRF cookie needed: opened from an email
    assert second.status_code == 400
    assert second.json()["error"]["code"] == "INVALID_TOKEN"
    owner = await api.app.state.store.admin_auth().find_by_email("fresh@example.com")
    assert owner is not None
    assert owner.email_verified is True


async def test_resend_verification_only_for_unverified_accounts(api: Api) -> None:
    cookies = await _login(api)  # the fixture owner is already verified
    before = len(api.mailer.sent)
    response = await api.client.post("/api/auth/verify-email/resend", headers=_auth(api, cookies))
    assert response.status_code == 202
    assert len(api.mailer.sent) == before

    await api.app.state.database["admins"].update_one(
        {"email": api.owner_email}, {"$set": {"email_verified": False}}
    )
    await api.client.post("/api/auth/verify-email/resend", headers=_auth(api, cookies))
    assert api.mailer.sent[-1][1] == "verify_email"


# ── Password forgot / reset / change ──


async def test_forgot_password_is_neutral(api: Api) -> None:
    known = await api.client.post("/api/auth/password/forgot", json={"email": api.owner_email})
    unknown = await api.client.post("/api/auth/password/forgot", json={"email": "x@example.com"})
    garbage = await api.client.post("/api/auth/password/forgot", json={"email": "not an email"})

    assert known.status_code == unknown.status_code == garbage.status_code == 202
    assert [t for _, t, _ in api.mailer.sent] == ["reset_password"]


async def test_reset_password_flow_revokes_every_session(api: Api) -> None:
    cookies = await _login(api)
    await api.client.post("/api/auth/password/forgot", json={"email": api.owner_email})
    token = api.mailer.last_token("reset_password")

    response = await api.client.post(
        "/api/auth/password/reset", json={"token": token, "password": NEW_PASSWORD}
    )

    assert response.status_code == 204
    refresh = await api.client.post("/api/auth/refresh", headers=_auth(api, cookies))
    assert refresh.status_code == 401  # all sessions revoked
    old = await api.client.post(
        "/api/auth/login", json={"email": api.owner_email, "password": PASSWORD}
    )
    assert old.status_code == 401
    await _login(api, password=NEW_PASSWORD)
    again = await api.client.post(
        "/api/auth/password/reset", json={"token": token, "password": "Yet-Another-Pass-99"}
    )
    assert again.status_code == 400  # single use


async def test_rejected_new_password_does_not_burn_the_reset_token(api: Api) -> None:
    await api.client.post("/api/auth/password/forgot", json={"email": api.owner_email})
    token = api.mailer.last_token("reset_password")

    weak = await api.client.post(
        "/api/auth/password/reset", json={"token": token, "password": "short"}
    )
    assert weak.status_code == 422
    ok = await api.client.post(
        "/api/auth/password/reset", json={"token": token, "password": NEW_PASSWORD}
    )
    assert ok.status_code == 204


async def test_expired_reset_token_is_refused(api: Api) -> None:
    await api.client.post("/api/auth/password/forgot", json={"email": api.owner_email})
    token = api.mailer.last_token("reset_password")
    await api.app.state.database["auth_tokens"].update_one(
        {"token_hash": hash_token(token)},
        {"$set": {"expires_at": datetime.now(UTC) - timedelta(seconds=1)}},
    )
    response = await api.client.post(
        "/api/auth/password/reset", json={"token": token, "password": NEW_PASSWORD}
    )
    assert response.status_code == 400


async def test_change_password_keeps_the_current_session_only(api: Api) -> None:
    other_device = await _login(api)
    cookies = await _login(api)

    wrong = await api.client.post(
        "/api/auth/password/change",
        json={"current_password": "nope-nope-nope", "new_password": NEW_PASSWORD},
        headers=_auth(api, cookies),
    )
    assert wrong.status_code == 400
    assert wrong.json()["error"]["code"] == "WRONG_PASSWORD"

    ok = await api.client.post(
        "/api/auth/password/change",
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
        headers=_auth(api, cookies),
    )
    assert ok.status_code == 204
    assert (
        await api.client.post("/api/auth/refresh", headers=_auth(api, cookies))
    ).status_code == 204
    assert (
        await api.client.post("/api/auth/refresh", headers=_auth(api, other_device))
    ).status_code == 401


async def test_change_password_requires_csrf(api: Api) -> None:
    cookies = await _login(api)
    response = await api.client.post(
        "/api/auth/password/change",
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
        headers=_auth(api, cookies, csrf=False),
    )
    assert response.status_code == 403


# ── Sessions ──


async def test_sessions_list_marks_the_current_one_and_hides_the_raw_user_agent(api: Api) -> None:
    await _login(api, ua="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) Safari/604.1")
    cookies = await _login(api)

    response = await api.client.get("/api/auth/sessions", headers=_auth(api, cookies))

    assert response.status_code == 200
    sessions = response.json()
    assert len(sessions) == 2
    assert sum(s["current"] for s in sessions) == 1
    assert {s["device"] for s in sessions} == {"Firefox · Windows", "Safari · iOS"}


async def test_revoke_one_session_and_all_others(api: Api) -> None:
    phone = await _login(api, ua="Mozilla/5.0 (Linux; Android 14) Chrome/130.0")
    laptop = await _login(api)
    tablet = await _login(api, ua="Mozilla/5.0 (iPad; CPU OS 17_0) Safari/604.1")
    sessions = (await api.client.get("/api/auth/sessions", headers=_auth(api, laptop))).json()
    phone_id = next(s["id"] for s in sessions if s["device"] == "Chrome · Android")

    one = await api.client.delete(f"/api/auth/sessions/{phone_id}", headers=_auth(api, laptop))
    assert one.status_code == 204
    assert (
        await api.client.post("/api/auth/refresh", headers=_auth(api, phone))
    ).status_code == 401

    others = await api.client.delete("/api/auth/sessions", headers=_auth(api, laptop))
    assert others.status_code == 204
    assert (
        await api.client.post("/api/auth/refresh", headers=_auth(api, tablet))
    ).status_code == 401
    assert (
        await api.client.post("/api/auth/refresh", headers=_auth(api, laptop))
    ).status_code == 204


async def test_cannot_revoke_another_administrators_session(api: Api) -> None:
    _, other_email = await api.add_tenant("beta")
    victim = await _login(api, email=other_email)
    victim_sessions = (
        await api.client.get("/api/auth/sessions", headers=_auth(api, victim))
    ).json()
    attacker = await _login(api)

    response = await api.client.delete(
        f"/api/auth/sessions/{victim_sessions[0]['id']}", headers=_auth(api, attacker)
    )

    assert response.status_code == 404
    assert (
        await api.client.post("/api/auth/refresh", headers=_auth(api, victim))
    ).status_code == 204

"""Tests for passwords, JWT, opaque tokens, CSRF and fingerprints."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest

from app.core import security
from app.core.config import Settings
from app.core.identity import EmailIdentity, ParticipantIdentity


@pytest.fixture
def settings() -> Settings:
    return Settings.model_validate(
        {"JWT_SECRET": "j" * 32, "CREDENTIAL_HMAC_KEY": "h" * 32, "IP_HASH_SALT": "s" * 16}
    )


def test_common_passwords_list_is_loaded_and_large() -> None:
    passwords = security.load_common_passwords()
    assert len(passwords) >= 10_000
    assert security.load_common_passwords() is passwords


def test_common_passwords_missing_file_fails_fast(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    monkeypatch.setattr(security, "_common_passwords", None)
    monkeypatch.setattr(security, "_COMMON_PASSWORDS_PATH", tmp_path / "missing.txt")
    with pytest.raises(RuntimeError, match="not found"):
        security.load_common_passwords()


def test_common_passwords_short_file_fails_fast(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    short = tmp_path / "short.txt"
    short.write_text("# header\nonly-one-password\n", encoding="utf-8")
    monkeypatch.setattr(security, "_common_passwords", None)
    monkeypatch.setattr(security, "_COMMON_PASSWORDS_PATH", short)
    with pytest.raises(RuntimeError, match="expected at least"):
        security.load_common_passwords()


@pytest.mark.parametrize(
    ("password", "message"),
    [
        ("short", "au moins 12"),
        ("x" * 129, "dépasser 128"),
        ("Alice@Example.com", "identique"),
    ],
)
def test_password_policy_rejections(password: str, message: str) -> None:
    with pytest.raises(security.PasswordPolicyError, match=message):
        security.validate_password(password, "alice@example.com")


def test_password_policy_rejects_common_password() -> None:
    common = sorted(security.load_common_passwords())[0]
    with pytest.raises(security.PasswordPolicyError, match="trop courant"):
        security.validate_password(common, "alice@example.com")


def test_password_policy_accepts_strong_password() -> None:
    security.validate_password("Correct-Horse-Battery-42!", "alice@example.com")


def test_hash_and_verify_password() -> None:
    hashed = security.hash_password("Correct-Horse-Battery-42!")
    assert hashed.startswith("$argon2id$")
    assert security.verify_password("Correct-Horse-Battery-42!", hashed)
    assert not security.verify_password("wrong", hashed)
    assert not security.verify_password("anything", None)
    assert not security.verify_password("anything", "not-a-hash")
    assert security.check_needs_rehash(hashed) is False


def test_access_token_round_trip(settings: Settings) -> None:
    token = security.create_access_token(settings, sub="a1", organization_id="o1", role="owner")
    payload = security.decode_access_token(settings, token)
    assert (payload["sub"], payload["organization_id"], payload["role"]) == ("a1", "o1", "owner")


def test_superadmin_token_has_null_organization(settings: Settings) -> None:
    token = security.create_access_token(settings, sub="s", organization_id=None, role="superadmin")
    assert security.decode_access_token(settings, token)["organization_id"] is None


def _forge(settings: Settings, **changes: Any) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "iss": "abaque",
        "aud": "abaque-admin",
        "sub": "a1",
        "organization_id": "o1",
        "role": "owner",
        "iat": now,
        "exp": now + timedelta(minutes=5),
        "jti": "x",
    }
    for key, value in changes.items():
        if value is None:
            payload.pop(key)
        else:
            payload[key] = value
    return jwt.encode(payload, settings.JWT_SECRET.get_secret_value(), algorithm="HS256")


@pytest.mark.parametrize(
    "changes",
    [
        {"role": "hacker"},
        {"organization_id": None},
        {"exp": datetime(2000, 1, 1, tzinfo=UTC)},
        {"aud": "other"},
        {"jti": None},
    ],
)
def test_invalid_access_tokens_are_rejected(settings: Settings, changes: dict[str, Any]) -> None:
    with pytest.raises(security.InvalidTokenError):
        security.decode_access_token(settings, _forge(settings, **changes))


def test_token_signed_with_another_key_is_rejected(settings: Settings) -> None:
    token = jwt.encode({"sub": "a"}, "k" * 32, algorithm="HS256")
    with pytest.raises(security.InvalidTokenError):
        security.decode_access_token(settings, token)


def test_opaque_tokens_and_csrf() -> None:
    token = security.generate_opaque_token()
    assert len(token) == 64
    assert security.hash_token(token) != token
    assert len(security.hash_token(token)) == 64
    csrf = security.generate_csrf_token()
    assert security.verify_csrf_token(csrf, csrf)
    assert not security.verify_csrf_token(csrf, "other")
    assert not security.verify_csrf_token(None, csrf)
    assert not security.verify_csrf_token(csrf, "")


def test_ip_hash_is_salted() -> None:
    assert security.hash_ip("1.2.3.4", "a" * 16) != security.hash_ip("1.2.3.4", "b" * 16)


def test_credential_fingerprint_is_stable_and_kind_prefixed(settings: Settings) -> None:
    first = security.compute_credential_fingerprint(settings, "v1", EmailIdentity("A@Example.com"))
    second = security.compute_credential_fingerprint(settings, "v1", EmailIdentity("a@example.com"))
    other_version = security.compute_credential_fingerprint(
        settings, "v2", EmailIdentity("a@example.com")
    )
    as_pid = security.compute_credential_fingerprint(
        settings, "v1", ParticipantIdentity("a@example.com")
    )
    assert first == second
    assert len({first, other_version, as_pid}) == 3

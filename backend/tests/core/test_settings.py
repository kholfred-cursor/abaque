"""Tests for configuration validation at application startup."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings

_VALID_VALUES: dict[str, object] = {
    "MONGODB_URI": "mongodb://mongo-test:27017/abaque_test?replicaSet=rs0",
    "DATABASE_NAME": "abaque_test",
    "JWT_SECRET": "j" * 32,
    "CREDENTIAL_HMAC_KEY": "h" * 32,
    "IP_HASH_SALT": "s" * 16,
}


def test_settings_rejects_a_missing_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each mandatory secret must be present before application startup."""
    for variable in ("JWT_SECRET", "CREDENTIAL_HMAC_KEY", "IP_HASH_SALT"):
        monkeypatch.delenv(variable, raising=False)

    with pytest.raises(ValidationError):
        Settings.model_validate(
            {"MONGODB_URI": _VALID_VALUES["MONGODB_URI"], "DATABASE_NAME": "abaque_test"}
        )


@pytest.mark.parametrize("secret_name", ["JWT_SECRET", "CREDENTIAL_HMAC_KEY", "IP_HASH_SALT"])
def test_settings_rejects_a_short_secret(secret_name: str) -> None:
    """Every secret has its documented minimum length."""
    values = {**_VALID_VALUES, secret_name: "too-short"}

    with pytest.raises(ValidationError):
        Settings.model_validate(values)


def test_settings_rejects_identical_secrets() -> None:
    """Independent secrets must never share the same value."""
    values = {**_VALID_VALUES, "CREDENTIAL_HMAC_KEY": _VALID_VALUES["JWT_SECRET"]}

    with pytest.raises(ValidationError):
        Settings.model_validate(values)


@pytest.mark.parametrize(
    ("overrides", "expected_message"),
    [
        ({"COOKIE_SECURE": False}, "COOKIE_SECURE"),
        ({"SEED_DEMO": True}, "SEED_DEMO"),
        ({"MONGODB_URI": "mongodb://mongo:27017/abaque?replicaSet=rs0"}, "MONGODB_URI"),
        ({"WEB_CONCURRENCY": 2}, "WEB_CONCURRENCY"),
    ],
)
def test_settings_enforces_production_guards(
    overrides: dict[str, object], expected_message: str
) -> None:
    """Production disallows unsafe cookie, seed, URI, and worker settings."""
    values = {
        **_VALID_VALUES,
        "ENVIRONMENT": "production",
        "COOKIE_SECURE": True,
        "SIGNUP_ENABLED": False,
        **overrides,
    }

    with pytest.raises(ValidationError, match=expected_message):
        Settings.model_validate(values)


def test_settings_resolves_production_signup_to_false() -> None:
    """Signup defaults to disabled in production when it is not explicitly set."""
    settings = Settings.model_validate(
        {
            **_VALID_VALUES,
            "ENVIRONMENT": "production",
            "COOKIE_SECURE": True,
        }
    )

    assert settings.SIGNUP_ENABLED is False

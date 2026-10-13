"""Application configuration via environment variables.

This module must be importable without a database connection,
so that create_app() and OpenAPI export work offline.
"""

from __future__ import annotations

import hashlib
import hmac
from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEV_MONGODB_URI = "mongodb://mongo:27017/abaque?replicaSet=rs0"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=None,
        extra="ignore",
    )

    # ── Environment ──
    ENVIRONMENT: Literal["development", "production"] = "development"

    # ── MongoDB ──
    MONGODB_URI: str = _DEV_MONGODB_URI
    DATABASE_NAME: str = "abaque"
    MONGO_SLOWMS: int = 200

    # ── Secrets (mandatory, startup fails without them) ──
    JWT_SECRET: SecretStr
    CREDENTIAL_HMAC_KEY: SecretStr
    IP_HASH_SALT: SecretStr

    # ── Auth ──
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14

    # ── Seed ──
    SEED_DEMO: bool = False

    # ── Signup ──
    # None means: resolved to True in dev, False in production
    SIGNUP_ENABLED: bool | None = None

    # ── Cookies ──
    COOKIE_SECURE: bool = False

    # ── Base URL ──
    APP_BASE_URL: str = "http://localhost:5173"

    # ── Rate limit backend ──
    RATE_LIMIT_BACKEND: Literal["memory"] = "memory"

    # ── Workers guard ──
    WEB_CONCURRENCY: int = 1

    @model_validator(mode="after")
    def _validate_secrets_and_env(self) -> Settings:
        jwt_val = self.JWT_SECRET.get_secret_value()
        hmac_val = self.CREDENTIAL_HMAC_KEY.get_secret_value()
        salt_val = self.IP_HASH_SALT.get_secret_value()

        if len(jwt_val) < 32:
            msg = "JWT_SECRET must be at least 32 characters"
            raise ValueError(msg)
        if len(hmac_val) < 32:
            msg = "CREDENTIAL_HMAC_KEY must be at least 32 characters"
            raise ValueError(msg)
        if len(salt_val) < 16:
            msg = "IP_HASH_SALT must be at least 16 characters"
            raise ValueError(msg)

        secrets = [jwt_val, hmac_val, salt_val]
        if len(set(secrets)) != len(secrets):
            msg = "JWT_SECRET, CREDENTIAL_HMAC_KEY and IP_HASH_SALT must all be different"
            raise ValueError(msg)

        is_prod = self.ENVIRONMENT == "production"

        if is_prod:
            if not self.COOKIE_SECURE:
                msg = "COOKIE_SECURE must be true in production"
                raise ValueError(msg)
            if self.SEED_DEMO:
                msg = "SEED_DEMO must be false in production"
                raise ValueError(msg)
            if self.MONGODB_URI == _DEV_MONGODB_URI:
                msg = "MONGODB_URI must not be the development default in production"
                raise ValueError(msg)

        # Resolve SIGNUP_ENABLED
        if self.SIGNUP_ENABLED is None:
            object.__setattr__(self, "SIGNUP_ENABLED", not is_prod)

        # Workers guard (D013)
        if self.WEB_CONCURRENCY > 1 and self.RATE_LIMIT_BACKEND == "memory":
            msg = (
                "WEB_CONCURRENCY > 1 is not allowed with RATE_LIMIT_BACKEND=memory. "
                "See DECISIONS.md D013."
            )
            raise ValueError(msg)

        return self

    @property
    def credential_key_id(self) -> str:
        """Non-reversible identifier for the current CREDENTIAL_HMAC_KEY.

        Used to detect key rotation while a version is open.
        First 16 hex chars of HMAC-SHA256(key, "abaque-key-id").
        """
        key = self.CREDENTIAL_HMAC_KEY.get_secret_value().encode()
        digest = hmac.new(key, b"abaque-key-id", hashlib.sha256).hexdigest()
        return digest[:16]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached singleton. Call this instead of instantiating Settings directly."""
    return Settings()

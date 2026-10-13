"""Password hashing, JWT encoding/decoding, token utilities, and fingerprinting.

Pure application logic. No database imports.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import argon2
import jwt

from app.core.config import Settings
from app.core.identity import Identity, normalize_email

logger = logging.getLogger(__name__)

# ── Password hashing ──

_hasher = argon2.PasswordHasher()

# Dummy hash for timing-safe rejection of unknown emails
_DUMMY_HASH = _hasher.hash("dummy-password-for-timing-equalization")

_COMMON_PASSWORDS_PATH = Path(__file__).parent / "data" / "common_passwords.txt"
_common_passwords: frozenset[str] | None = None

_MIN_COMMON_PASSWORDS = 10_000


def load_common_passwords() -> frozenset[str]:
    """Load and cache the common passwords list.

    Must be called in the lifespan to fail fast at startup.
    Source: SecLists (MIT license) — see backend/scripts/build_common_passwords.py.

    Raises RuntimeError if the file is missing or too short.
    """
    global _common_passwords
    if _common_passwords is not None:
        return _common_passwords

    if not _COMMON_PASSWORDS_PATH.exists():
        msg = (
            f"Common passwords file not found: {_COMMON_PASSWORDS_PATH}. "
            "Run 'python scripts/build_common_passwords.py' first."
        )
        raise RuntimeError(msg)

    passwords = frozenset(
        line.strip().lower()
        for line in _COMMON_PASSWORDS_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    )

    if len(passwords) < _MIN_COMMON_PASSWORDS:
        msg = (
            f"Common passwords file has only {len(passwords)} entries, "
            f"expected at least {_MIN_COMMON_PASSWORDS}. "
            "Run 'python scripts/build_common_passwords.py' with a larger source."
        )
        raise RuntimeError(msg)

    _common_passwords = passwords
    return _common_passwords


class PasswordPolicyError(ValueError):
    """Raised when a password does not meet the policy."""


def validate_password(password: str, email: str) -> None:
    """Validate password against the policy.

    Compares with the NORMALIZED email. Raises PasswordPolicyError.
    """
    if len(password) < 12:
        raise PasswordPolicyError("Le mot de passe doit contenir au moins 12 caractères.")
    if len(password) > 128:
        raise PasswordPolicyError("Le mot de passe ne doit pas dépasser 128 caractères.")

    normalized = normalize_email(email)
    if password.lower() == normalized.lower():
        raise PasswordPolicyError("Le mot de passe ne peut pas être identique à l'adresse e-mail.")
    if password.lower() in load_common_passwords():
        raise PasswordPolicyError("Ce mot de passe est trop courant.")


def hash_password(password: str) -> str:
    """Hash a password with argon2id."""
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    """Verify a password against its hash.

    Returns False on ANY argon2 error (mismatch, invalid hash, etc.).
    When password_hash is None (unknown email), verifies against a dummy
    hash to equalize response time and prevent user enumeration.
    """
    target = password_hash if password_hash is not None else _DUMMY_HASH
    try:
        return _hasher.verify(target, password)
    except argon2.exceptions.VerificationError:
        # VerifyMismatchError is a subclass of VerificationError
        return False
    except argon2.exceptions.InvalidHashError:
        return False


def check_needs_rehash(password_hash: str) -> bool:
    """Check if a password hash needs to be rehashed (parameters changed)."""
    return _hasher.check_needs_rehash(password_hash)


# ── JWT ──

_ALGORITHM = "HS256"
_ISSUER = "abaque"
_AUDIENCE = "abaque-admin"
_VALID_ROLES = {"owner", "animator", "superadmin"}


def create_access_token(
    settings: Settings,
    *,
    sub: str,
    organization_id: str | None,
    role: str,
) -> str:
    """Create a signed JWT access token."""
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "iss": _ISSUER,
        "aud": _AUDIENCE,
        "sub": sub,
        "organization_id": organization_id,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(
        payload,
        settings.JWT_SECRET.get_secret_value(),
        algorithm=_ALGORITHM,
    )


class InvalidTokenError(Exception):
    """Raised when a JWT token is invalid for any reason."""


def decode_access_token(settings: Settings, token: str) -> dict[str, Any]:
    """Decode and validate a JWT access token.

    Raises InvalidTokenError on any validation failure.
    organization_id is NOT in require (it may be null for superadmin):
    its presence is checked manually.
    """
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.JWT_SECRET.get_secret_value(),
            algorithms=[_ALGORITHM],
            issuer=_ISSUER,
            audience=_AUDIENCE,
            leeway=timedelta(seconds=10),
            options={"require": ["exp", "iat", "sub", "iss", "aud", "jti"]},
        )
    except jwt.InvalidTokenError as exc:
        raise InvalidTokenError(str(exc)) from exc

    if payload.get("role") not in _VALID_ROLES:
        raise InvalidTokenError("Invalid role claim")

    if "organization_id" not in payload:
        raise InvalidTokenError("Missing organization_id claim")

    return payload


# ── Opaque tokens ──


def generate_opaque_token() -> str:
    """Generate a 256-bit random opaque token, hex-encoded."""
    return secrets.token_hex(32)


def hash_token(token: str) -> str:
    """Hash an opaque token with SHA-256 for storage."""
    return hashlib.sha256(token.encode()).hexdigest()


# ── CSRF ──


def generate_csrf_token() -> str:
    """Generate a random CSRF token."""
    return secrets.token_hex(32)


def verify_csrf_token(cookie_value: str | None, header_value: str | None) -> bool:
    """Constant-time comparison of CSRF cookie and header values.

    Returns False if either value is absent or empty.
    """
    if not cookie_value or not header_value:
        return False
    return hmac.compare_digest(cookie_value, header_value)


# ── IP hashing ──


def hash_ip(ip: str, salt: str) -> str:
    """Hash an IP address with HMAC-SHA256 for rate limiting."""
    return hmac.new(salt.encode(), ip.encode(), hashlib.sha256).hexdigest()


# ── Credential fingerprint ──


def compute_credential_fingerprint(
    settings: Settings,
    version_id: str,
    identity: Identity,
) -> str:
    """Compute HMAC-SHA256 fingerprint for credential_uses.

    The identity is already normalized at construction (EmailIdentity.__post_init__).
    Message format: "v1|<version_id>|<kind>:<value>"
    The kind prefix prevents collisions between emails and participant IDs.
    """
    message = f"v1|{version_id}|{identity.kind}:{identity.value}"
    return hmac.new(
        settings.CREDENTIAL_HMAC_KEY.get_secret_value().encode(),
        message.encode(),
        hashlib.sha256,
    ).hexdigest()

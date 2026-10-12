"""Account lifecycle (block 5b): signup, email verification, password reset and change,
session management. Responses that could reveal whether an account exists are neutral."""

from __future__ import annotations

import re
import secrets
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.core.config import Settings
from app.core.identity import InvalidEmailError, normalize_email
from app.core.security import (
    generate_opaque_token,
    hash_ip,
    hash_password,
    hash_token,
    validate_password,
    verify_password,
)
from app.domain.errors import EmailAlreadyRegistered
from app.domain.models import Admin, AdminCreate, OrganizationCreate
from app.repositories.mongo.store import MongoStore
from app.services.auth import RateLimited
from app.services.mailer import Mailer
from app.services.rate_limit import RateLimiter

HOUR = 3600
SENSITIVE_LIMIT_PER_IP = 5  # signup, password/forgot, verify-email/resend
VERIFY_EMAIL_TTL = timedelta(hours=24)
RESET_PASSWORD_TTL = timedelta(minutes=30)


class SignupDisabled(Exception):  # noqa: N818
    pass


class InvalidToken(Exception):  # noqa: N818
    """Unknown, expired, already used, or wrong-purpose token."""


class WrongPassword(Exception):  # noqa: N818
    pass


@dataclass(frozen=True)
class SessionView:
    id: str
    created_at: datetime
    last_used_at: datetime | None
    device: str | None
    current: bool


def slugify(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    base = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")[:40] or "organisation"
    # Random suffix: slugs never reveal whether a name is already taken.
    return f"{base}-{secrets.token_hex(3)}"


class AccountService:
    def __init__(
        self, store: MongoStore, settings: Settings, rate_limiter: RateLimiter, mailer: Mailer
    ) -> None:
        self.store = store
        self.settings = settings
        self.rate_limiter = rate_limiter
        self.mailer = mailer

    async def _throttle(self, action: str, client_ip: str) -> None:
        key = f"{action}:{hash_ip(client_ip, self.settings.IP_HASH_SALT.get_secret_value())}"
        wait = await self.rate_limiter.retry_after(key, SENSITIVE_LIMIT_PER_IP, HOUR)
        if wait is not None:
            raise RateLimited(wait)
        await self.rate_limiter.record(key, HOUR)

    def _link(self, path: str, token: str) -> str:
        return f"{self.settings.APP_BASE_URL.rstrip('/')}{path}?token={token}"

    async def _send_verification(self, admin: Admin) -> None:
        token = generate_opaque_token()
        await self.store.auth_tokens().create(
            admin.id, "verify_email", hash_token(token), datetime.now(UTC) + VERIFY_EMAIL_TTL
        )
        await self.mailer.send(
            admin.email, "verify_email", {"link": self._link("/verifier-email", token)}
        )

    # ── Signup & verification ──

    async def signup(
        self, organization_name: str, email: str, password: str, client_ip: str
    ) -> None:
        if not self.settings.SIGNUP_ENABLED:
            raise SignupDisabled
        await self._throttle("signup", client_ip)
        normalized = normalize_email(email)  # InvalidEmailError -> 422
        validate_password(password, normalized)  # PasswordPolicyError -> 422
        password_hash = hash_password(password)  # always hashed: same cost either way
        try:
            _, owner = await self.store.provisioning().create_with_owner(
                OrganizationCreate(name=organization_name, slug=slugify(organization_name)),
                AdminCreate(email=normalized, password_hash=password_hash),
            )
        except EmailAlreadyRegistered:
            await self.mailer.send(
                normalized,
                "account_exists",
                {"link": f"{self.settings.APP_BASE_URL.rstrip('/')}/connexion"},
            )
            return
        await self._send_verification(owner)

    async def verify_email(self, token: str) -> None:
        admin_id = await self.store.auth_tokens().consume(hash_token(token), "verify_email")
        if admin_id is None:
            raise InvalidToken
        await self.store.admin_auth().mark_email_verified(admin_id)

    async def resend_verification(self, admin: Admin, client_ip: str) -> None:
        await self._throttle("verify-resend", client_ip)
        if not admin.email_verified:
            await self._send_verification(admin)

    # ── Password ──

    async def forgot_password(self, email: str, client_ip: str) -> None:
        await self._throttle("forgot", client_ip)
        try:
            admin = await self.store.admin_auth().find_by_email(email)
        except InvalidEmailError:
            return
        if admin is None:
            return
        token = generate_opaque_token()
        await self.store.auth_tokens().create(
            admin.id, "reset_password", hash_token(token), datetime.now(UTC) + RESET_PASSWORD_TTL
        )
        await self.mailer.send(
            admin.email, "reset_password", {"link": self._link("/reinitialiser", token)}
        )

    async def reset_password(self, token: str, new_password: str) -> None:
        tokens = self.store.auth_tokens()
        token_hash = hash_token(token)
        admin_id = await tokens.peek(token_hash, "reset_password")
        admin = None if admin_id is None else await self.store.admin_auth().get_by_id(admin_id)
        if admin is None:
            raise InvalidToken
        # Policy first: a rejected password must not burn the single-use token.
        validate_password(new_password, admin.email)
        if await tokens.consume(token_hash, "reset_password") is None:
            raise InvalidToken  # consumed concurrently
        await self.store.admin_auth().set_password_hash(admin.id, hash_password(new_password))
        await tokens.delete_for_admin(admin.id, "reset_password")
        await self.store.sessions().revoke_all_for_admin(admin.id)

    async def change_password(
        self, admin: Admin, current: str, new: str, current_refresh_token: str | None
    ) -> None:
        if not verify_password(current, admin.password_hash):
            raise WrongPassword
        validate_password(new, admin.email)
        await self.store.admin_auth().set_password_hash(admin.id, hash_password(new))
        keep = None if not current_refresh_token else hash_token(current_refresh_token)
        await self.store.sessions().revoke_all_except(admin.id, keep)

    # ── Sessions ──

    async def list_sessions(
        self, admin: Admin, current_refresh_token: str | None
    ) -> list[SessionView]:
        current = None if not current_refresh_token else hash_token(current_refresh_token)
        return [
            SessionView(
                id=s.id,
                created_at=s.created_at,
                last_used_at=s.last_used_at,
                device=s.user_agent_hint,
                current=s.token_hash == current,
            )
            for s in await self.store.sessions().list_active(admin.id)
        ]

    async def revoke_session(self, admin: Admin, session_id: str) -> None:
        await self.store.sessions().revoke_by_id(admin.id, session_id)

    async def revoke_other_sessions(self, admin: Admin, current_refresh_token: str | None) -> int:
        keep = None if not current_refresh_token else hash_token(current_refresh_token)
        return await self.store.sessions().revoke_all_except(admin.id, keep)

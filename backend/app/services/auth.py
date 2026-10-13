"""Administrator authentication: login, refresh-token rotation, logout.

Pure orchestration over repositories and app.core.security; no HTTP types here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.core.config import Settings
from app.core.identity import InvalidEmailError, normalize_email
from app.core.security import (
    check_needs_rehash,
    create_access_token,
    generate_csrf_token,
    generate_opaque_token,
    hash_ip,
    hash_password,
    hash_token,
    verify_password,
)
from app.domain.errors import NotFound
from app.domain.models import Admin
from app.domain.sessions import SessionReuseDetected
from app.repositories.mongo.store import MongoStore
from app.services.rate_limit import RateLimiter

LOGIN_WINDOW_SECONDS = 15 * 60
LOGIN_LIMIT_PER_IP = 10
LOGIN_LIMIT_PER_ACCOUNT = 5


def describe_device(user_agent: str | None) -> str | None:
    """Short, non-identifying description such as "Firefox · Windows" (never the raw UA)."""
    if not user_agent:
        return None
    browser = next(
        (
            name
            for marker, name in (
                ("Edg/", "Edge"),
                ("OPR/", "Opera"),
                ("Firefox/", "Firefox"),
                ("Chrome/", "Chrome"),
                ("Safari/", "Safari"),
            )
            if marker in user_agent
        ),
        "Navigateur",
    )
    system = next(
        (
            name
            for marker, name in (
                ("Windows", "Windows"),
                ("Android", "Android"),
                ("iPhone", "iOS"),
                ("iPad", "iPadOS"),
                ("Mac OS", "macOS"),
                ("Linux", "Linux"),
            )
            if marker in user_agent
        ),
        "système inconnu",
    )
    return f"{browser} · {system}"


class InvalidCredentials(Exception):  # noqa: N818
    """Unknown email or wrong password: deliberately indistinguishable."""


class RateLimited(Exception):  # noqa: N818
    def __init__(self, retry_after: int) -> None:
        super().__init__("rate limited")
        self.retry_after = retry_after


class SessionInvalid(Exception):  # noqa: N818
    """Refresh token absent, unknown, revoked, expired, or replayed."""


@dataclass(frozen=True)
class IssuedTokens:
    admin: Admin
    access_token: str
    refresh_token: str
    csrf_token: str


class AuthService:
    def __init__(self, store: MongoStore, settings: Settings, rate_limiter: RateLimiter) -> None:
        self.settings = settings
        self.admins = store.admin_auth()
        self.sessions = store.sessions()
        self.rate_limiter = rate_limiter

    def _key(self, kind: str, value: str) -> str:
        return f"{kind}:{hash_ip(value, self.settings.IP_HASH_SALT.get_secret_value())}"

    async def _issue(self, admin: Admin, refresh_token: str) -> IssuedTokens:
        access = create_access_token(
            self.settings, sub=admin.id, organization_id=admin.organization_id, role=admin.role
        )
        return IssuedTokens(admin, access, refresh_token, generate_csrf_token())

    def _refresh_expiry(self) -> datetime:
        return datetime.now(UTC) + timedelta(days=self.settings.REFRESH_TOKEN_EXPIRE_DAYS)

    async def login(
        self, email: str, password: str, client_ip: str, user_agent: str | None = None
    ) -> IssuedTokens:
        try:
            normalized = normalize_email(email)
        except InvalidEmailError:
            normalized = None
        ip_key = self._key("login-ip", client_ip)
        account_key = self._key("login-account", normalized or "invalid")

        for key, limit in ((ip_key, LOGIN_LIMIT_PER_IP), (account_key, LOGIN_LIMIT_PER_ACCOUNT)):
            wait = await self.rate_limiter.retry_after(key, limit, LOGIN_WINDOW_SECONDS)
            if wait is not None:
                raise RateLimited(wait)

        admin = None if normalized is None else await self.admins.find_by_email(normalized)
        # verify_password(None) checks a dummy hash: same timing for unknown accounts.
        valid = verify_password(password, None if admin is None else admin.password_hash)
        if admin is None or not valid:
            await self.rate_limiter.record(ip_key, LOGIN_WINDOW_SECONDS)
            await self.rate_limiter.record(account_key, LOGIN_WINDOW_SECONDS)
            raise InvalidCredentials

        await self.rate_limiter.reset(account_key)
        if check_needs_rehash(admin.password_hash):
            admin = await self.admins.set_password_hash(admin.id, hash_password(password))

        refresh_token = generate_opaque_token()
        await self.sessions.create(
            admin.id,
            hash_token(refresh_token),
            self._refresh_expiry(),
            user_agent_hint=describe_device(user_agent),
        )
        return await self._issue(admin, refresh_token)

    async def refresh(self, refresh_token: str | None) -> IssuedTokens:
        """Rotate the refresh token. ConcurrentRotation propagates (benign two-tab race)."""
        if not refresh_token:
            raise SessionInvalid
        new_token = generate_opaque_token()
        try:
            session = await self.sessions.rotate(
                hash_token(refresh_token), hash_token(new_token), self._refresh_expiry()
            )
        except (NotFound, SessionReuseDetected) as exc:
            raise SessionInvalid from exc
        admin = await self.admins.get_by_id(session.admin_id)
        if admin is None:
            await self.sessions.revoke(hash_token(new_token))
            raise SessionInvalid
        return await self._issue(admin, new_token)

    async def logout(self, refresh_token: str | None) -> None:
        if refresh_token:
            await self.sessions.revoke(hash_token(refresh_token))

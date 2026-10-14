"""FastAPI dependencies: settings, database, authentication, tenant scope, CSRF."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, Request

from app.api.cookies import ACCESS_COOKIE, CSRF_COOKIE
from app.api.errors import NOT_AUTHENTICATED, ApiError
from app.core.config import Settings
from app.core.security import InvalidTokenError, decode_access_token, verify_csrf_token
from app.domain.models import Admin, AdminRole, TenantContext
from app.repositories.mongo.admins import AdminRepository
from app.repositories.mongo.organizations import OrganizationRepository
from app.repositories.mongo.store import MongoStore
from app.services.account import AccountService
from app.services.auth import AuthService
from app.services.content import ContentService
from app.services.mailer import Mailer
from app.services.rate_limit import RateLimiter

UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
# Protected by SameSite + rate limiting instead (no session exists yet).
# verify-email and password/reset carry a secret single-use token in the body, which a
# cross-site attacker cannot know; the CSRF cookie may not even exist yet (link opened
# from an email, no session). D031.
CSRF_EXEMPT_PATHS = frozenset(
    {
        "/api/auth/login",
        "/api/auth/signup",
        "/api/auth/password/forgot",
        "/api/auth/verify-email",
        "/api/auth/password/reset",
    }
)


def get_settings_dep(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_store(request: Request) -> MongoStore:
    store: MongoStore = request.app.state.store
    return store


def get_rate_limiter(request: Request) -> RateLimiter:
    limiter: RateLimiter = request.app.state.rate_limiter
    return limiter


def get_mailer(request: Request) -> Mailer:
    mailer: Mailer = request.app.state.mailer
    return mailer


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
StoreDep = Annotated[MongoStore, Depends(get_store)]


def get_auth_service(
    store: StoreDep,
    settings: SettingsDep,
    rate_limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> AuthService:
    return AuthService(store, settings, rate_limiter)


def get_account_service(
    store: StoreDep,
    settings: SettingsDep,
    rate_limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
    mailer: Annotated[Mailer, Depends(get_mailer)],
) -> AccountService:
    return AccountService(store, settings, rate_limiter, mailer)


async def csrf_protect(request: Request) -> None:
    """Double-submit check on every state-changing request (constant-time comparison)."""
    if request.method not in UNSAFE_METHODS or request.url.path in CSRF_EXEMPT_PATHS:
        return
    if not verify_csrf_token(request.cookies.get(CSRF_COOKIE), request.headers.get("X-CSRF-Token")):
        raise ApiError(403, "CSRF_FAILED", "Requête refusée (jeton CSRF invalide).")


async def current_admin(request: Request, settings: SettingsDep, store: StoreDep) -> Admin:
    token = request.cookies.get(ACCESS_COOKIE)
    if not token:
        raise NOT_AUTHENTICATED
    try:
        claims = decode_access_token(settings, token)
    except InvalidTokenError as exc:
        raise NOT_AUTHENTICATED from exc
    admin = await store.admin_auth().get_by_id(str(claims["sub"]))
    if admin is None:
        raise NOT_AUTHENTICATED
    return admin


CurrentAdmin = Annotated[Admin, Depends(current_admin)]


async def require_verified(admin: CurrentAdmin) -> Admin:
    if not admin.email_verified:
        raise ApiError(
            403, "EMAIL_NOT_VERIFIED", "Veuillez d'abord confirmer votre adresse e-mail."
        )
    return admin


def require_role(*roles: AdminRole) -> Callable[[Admin], Awaitable[Admin]]:
    async def dependency(admin: CurrentAdmin) -> Admin:
        if admin.role not in roles:
            raise ApiError(403, "FORBIDDEN", "Action non autorisée.")
        return admin

    return dependency


async def current_org(admin: CurrentAdmin) -> TenantContext:
    """The ONLY place a TenantContext is built: from the authenticated account, never
    from anything the client sends."""
    if admin.organization_id is None:  # platform superadmin: no organization routes
        raise ApiError(403, "FORBIDDEN", "Action non autorisée.")
    return TenantContext(organization_id=admin.organization_id, admin_id=admin.id, role=admin.role)


TenantDep = Annotated[TenantContext, Depends(current_org)]


def organization_repository(store: StoreDep, tenant: TenantDep) -> OrganizationRepository:
    return store.organizations(tenant)


def admin_repository(store: StoreDep, tenant: TenantDep) -> AdminRepository:
    return store.admins(tenant)


async def verified_org(
    _: Annotated[Admin, Depends(require_verified)], tenant: TenantDep
) -> TenantContext:
    """Tenant scope for content routes: the account must have confirmed its email."""
    return tenant


def get_content_service(
    store: StoreDep,
    settings: SettingsDep,
    tenant: Annotated[TenantContext, Depends(verified_org)],
) -> ContentService:
    return ContentService(store, tenant, settings)


ContentDep = Annotated[ContentService, Depends(get_content_service)]

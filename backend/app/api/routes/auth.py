"""Authentication routes (lot 0, block 5a): login, refresh, logout, me."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field

from app.api.cookies import REFRESH_COOKIE, clear_auth_cookies, set_auth_cookies
from app.api.deps import CurrentAdmin, SettingsDep, StoreDep, get_auth_service
from app.api.errors import ApiError, error_response, responses
from app.domain.models import TenantContext
from app.domain.sessions import ConcurrentRotation
from app.services.auth import AuthService, InvalidCredentials, RateLimited, SessionInvalid

router = APIRouter(prefix="/auth", tags=["auth"])
AuthDep = Annotated[AuthService, Depends(get_auth_service)]


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class OrganizationSummary(BaseModel):
    id: str
    name: str
    plan_code: Literal["demo", "trial", "standard"]


class MeResponse(BaseModel):
    id: str
    email: str
    role: Literal["owner", "animator", "superadmin"]
    email_verified: bool
    organization: OrganizationSummary | None


def _client_ip(request: Request) -> str:
    # Resolved by uvicorn from trusted proxies only; X-Forwarded-For is never read here.
    return request.client.host if request.client is not None else "unknown"


async def _me(admin: CurrentAdmin, store: StoreDep) -> MeResponse:
    organization = None
    if admin.organization_id is not None:
        tenant = TenantContext(
            organization_id=admin.organization_id, admin_id=admin.id, role=admin.role
        )
        org = await store.organizations(tenant).get_current()
        organization = OrganizationSummary(id=org.id, name=org.name, plan_code=org.plan_code)
    return MeResponse(
        id=admin.id,
        email=admin.email,
        role=admin.role,
        email_verified=admin.email_verified,
        organization=organization,
    )


@router.post("/login", response_model=MeResponse, responses=responses(401, 422, 429))
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    service: AuthDep,
    settings: SettingsDep,
    store: StoreDep,
) -> MeResponse:
    try:
        issued = await service.login(payload.email, payload.password, _client_ip(request))
    except RateLimited as exc:
        raise ApiError(
            429,
            "RATE_LIMITED",
            "Trop de tentatives. Réessayez plus tard.",
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc
    except InvalidCredentials as exc:
        raise ApiError(401, "INVALID_CREDENTIALS", "Identifiants incorrects.") from exc
    set_auth_cookies(
        response,
        settings,
        access_token=issued.access_token,
        refresh_token=issued.refresh_token,
        csrf_token=issued.csrf_token,
    )
    return await _me(issued.admin, store)


@router.post("/refresh", status_code=204, responses=responses(401, 403, 409))
async def refresh(request: Request, service: AuthDep, settings: SettingsDep) -> Response:
    try:
        issued = await service.refresh(request.cookies.get(REFRESH_COOKIE))
    except ConcurrentRotation as exc:
        # Benign two-tab race (D029): cookies untouched, the client simply retries.
        raise ApiError(409, "SESSION_ROTATED", "Session déjà renouvelée, réessayez.") from exc
    except SessionInvalid:
        response = Response(status_code=401)
        clear_auth_cookies(response, settings)
        cleared = error_response(401, "SESSION_REVOKED", "Session expirée. Reconnectez-vous.")
        for header in response.headers.getlist("set-cookie"):
            cleared.headers.append("set-cookie", header)
        return cleared
    response = Response(status_code=204)
    set_auth_cookies(
        response,
        settings,
        access_token=issued.access_token,
        refresh_token=issued.refresh_token,
        csrf_token=issued.csrf_token,
    )
    return response


@router.post("/logout", status_code=204, responses=responses(403))
async def logout(request: Request, service: AuthDep, settings: SettingsDep) -> Response:
    await service.logout(request.cookies.get(REFRESH_COOKIE))
    response = Response(status_code=204)
    clear_auth_cookies(response, settings)
    return response


@router.get("/me", response_model=MeResponse, responses=responses(401))
async def me(admin: CurrentAdmin, store: StoreDep) -> MeResponse:
    return await _me(admin, store)

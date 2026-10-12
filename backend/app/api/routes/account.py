"""Account routes (lot 0, block 5b): signup, email verification, password, sessions."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field

from app.api.cookies import REFRESH_COOKIE
from app.api.deps import CurrentAdmin, get_account_service
from app.api.errors import ApiError, responses
from app.api.routes.auth import client_ip
from app.core.identity import InvalidEmailError
from app.services.account import AccountService, InvalidToken, SignupDisabled, WrongPassword
from app.services.auth import RateLimited

router = APIRouter(prefix="/auth", tags=["account"])
AccountDep = Annotated[AccountService, Depends(get_account_service)]


def _rate_limited(exc: RateLimited) -> ApiError:
    return ApiError(
        429,
        "RATE_LIMITED",
        "Trop de demandes. Réessayez plus tard.",
        headers={"Retry-After": str(exc.retry_after)},
    )


INVALID_TOKEN = ApiError(400, "INVALID_TOKEN", "Ce lien n'est plus valide. Demandez-en un nouveau.")


class SignupRequest(BaseModel):
    organization_name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class TokenRequest(BaseModel):
    token: str = Field(min_length=16, max_length=256)


class ForgotRequest(BaseModel):
    email: str = Field(min_length=1, max_length=254)


class ResetRequest(BaseModel):
    token: str = Field(min_length=16, max_length=256)
    password: str = Field(min_length=1, max_length=256)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=1, max_length=256)


class SessionResponse(BaseModel):
    id: str
    created_at: datetime
    last_used_at: datetime | None
    device: str | None
    current: bool


@router.post("/signup", status_code=202, responses=responses(403, 422, 429))
async def signup(payload: SignupRequest, request: Request, service: AccountDep) -> Response:
    """Always 202 when accepted, whether or not the email already has an account."""
    try:
        await service.signup(
            payload.organization_name, payload.email, payload.password, client_ip(request)
        )
    except SignupDisabled as exc:
        raise ApiError(403, "SIGNUP_DISABLED", "Les inscriptions sont fermées.") from exc
    except RateLimited as exc:
        raise _rate_limited(exc) from exc
    except InvalidEmailError as exc:
        raise ApiError(422, "VALIDATION_ERROR", "Adresse e-mail invalide.") from exc
    return Response(status_code=202)


@router.post("/verify-email", status_code=204, responses=responses(400, 422))
async def verify_email(payload: TokenRequest, service: AccountDep) -> Response:
    try:
        await service.verify_email(payload.token)
    except InvalidToken as exc:
        raise INVALID_TOKEN from exc
    return Response(status_code=204)


@router.post("/verify-email/resend", status_code=202, responses=responses(401, 403, 429))
async def resend_verification(
    admin: CurrentAdmin, request: Request, service: AccountDep
) -> Response:
    try:
        await service.resend_verification(admin, client_ip(request))
    except RateLimited as exc:
        raise _rate_limited(exc) from exc
    return Response(status_code=202)


@router.post("/password/forgot", status_code=202, responses=responses(422, 429))
async def forgot_password(
    payload: ForgotRequest, request: Request, service: AccountDep
) -> Response:
    """Always 202: never reveals whether the account exists."""
    try:
        await service.forgot_password(payload.email, client_ip(request))
    except RateLimited as exc:
        raise _rate_limited(exc) from exc
    return Response(status_code=202)


@router.post("/password/reset", status_code=204, responses=responses(400, 422))
async def reset_password(payload: ResetRequest, service: AccountDep) -> Response:
    try:
        await service.reset_password(payload.token, payload.password)
    except InvalidToken as exc:
        raise INVALID_TOKEN from exc
    return Response(status_code=204)


@router.post("/password/change", status_code=204, responses=responses(400, 401, 403, 422))
async def change_password(
    payload: ChangePasswordRequest, admin: CurrentAdmin, request: Request, service: AccountDep
) -> Response:
    try:
        await service.change_password(
            admin,
            payload.current_password,
            payload.new_password,
            request.cookies.get(REFRESH_COOKIE),
        )
    except WrongPassword as exc:
        # 400, not 401: a 401 would make the front try a session refresh.
        raise ApiError(400, "WRONG_PASSWORD", "Mot de passe actuel incorrect.") from exc
    return Response(status_code=204)


@router.get("/sessions", response_model=list[SessionResponse], responses=responses(401))
async def list_sessions(
    admin: CurrentAdmin, request: Request, service: AccountDep
) -> list[SessionResponse]:
    views = await service.list_sessions(admin, request.cookies.get(REFRESH_COOKIE))
    return [SessionResponse(**view.__dict__) for view in views]


@router.delete("/sessions/{session_id}", status_code=204, responses=responses(401, 403, 404))
async def revoke_session(session_id: str, admin: CurrentAdmin, service: AccountDep) -> Response:
    await service.revoke_session(admin, session_id)
    return Response(status_code=204)


@router.delete("/sessions", status_code=204, responses=responses(401, 403))
async def revoke_other_sessions(
    admin: CurrentAdmin, request: Request, service: AccountDep
) -> Response:
    await service.revoke_other_sessions(admin, request.cookies.get(REFRESH_COOKIE))
    return Response(status_code=204)

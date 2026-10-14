"""Single error format for the API: {"error": {"code", "message"}}.

Codes are stable English identifiers; messages are French and safe to display.
Domain exceptions are translated here and nowhere else.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.core.security import PasswordPolicyError
from app.domain.errors import NotFound, RuleViolation
from app.entitlements.checker import FeatureNotAllowed, LimitReached


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


class ApiError(Exception):
    """An error that maps directly to an HTTP status and a stable code."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.headers = headers


def error_response(
    status_code: int, code: str, message: str, headers: dict[str, str] | None = None
) -> JSONResponse:
    body = ErrorResponse(error=ErrorDetail(code=code, message=message))
    return JSONResponse(status_code=status_code, content=body.model_dump(), headers=headers)


def responses(*status_codes: int) -> dict[int | str, dict[str, object]]:
    """OpenAPI documentation of the error responses a route can return."""
    return {code: {"model": ErrorResponse} for code in status_codes}


NOT_AUTHENTICATED = ApiError(401, "NOT_AUTHENTICATED", "Veuillez vous connecter.")


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return error_response(exc.status_code, exc.code, exc.message, exc.headers)

    @app.exception_handler(NotFound)
    async def _not_found(_: Request, __: NotFound) -> JSONResponse:
        return error_response(404, "NOT_FOUND", "Ressource introuvable.")

    @app.exception_handler(RuleViolation)
    async def _rule(_: Request, exc: RuleViolation) -> JSONResponse:
        return error_response(exc.status_code, exc.code, exc.message)

    @app.exception_handler(LimitReached)
    async def _limit(_: Request, __: LimitReached) -> JSONResponse:
        # D020: 403 rather than 402 (402 is reserved and poorly handled by clients).
        return error_response(403, "LIMIT_REACHED", "Limite de votre offre atteinte.")

    @app.exception_handler(FeatureNotAllowed)
    async def _feature(_: Request, __: FeatureNotAllowed) -> JSONResponse:
        return error_response(
            403, "FEATURE_NOT_ALLOWED", "Fonctionnalité non disponible avec votre offre."
        )

    @app.exception_handler(PasswordPolicyError)
    async def _password(_: Request, exc: PasswordPolicyError) -> JSONResponse:
        return error_response(422, "PASSWORD_POLICY", str(exc))

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, __: RequestValidationError) -> JSONResponse:
        # The submitted values are never echoed back (they may contain secrets).
        return error_response(422, "VALIDATION_ERROR", "Données invalides.")

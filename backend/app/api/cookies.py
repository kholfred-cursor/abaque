"""The three authentication cookies, with exactly the attributes of the specification."""

from __future__ import annotations

from fastapi import Response

from app.core.config import Settings

ACCESS_COOKIE = "abq_access"
REFRESH_COOKIE = "abq_refresh"
CSRF_COOKIE = "abq_csrf"

ACCESS_PATH = "/api"
REFRESH_PATH = "/api/auth"
CSRF_PATH = "/"


def set_auth_cookies(
    response: Response,
    settings: Settings,
    *,
    access_token: str,
    refresh_token: str,
    csrf_token: str,
) -> None:
    refresh_max_age = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600
    response.set_cookie(
        ACCESS_COOKIE,
        access_token,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path=ACCESS_PATH,
        secure=settings.COOKIE_SECURE,
        httponly=True,
        samesite="lax",
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        max_age=refresh_max_age,
        path=REFRESH_PATH,
        secure=settings.COOKIE_SECURE,
        httponly=True,
        samesite="strict",
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf_token,
        max_age=refresh_max_age,
        path=CSRF_PATH,
        secure=settings.COOKIE_SECURE,
        httponly=False,  # read by the front to send X-CSRF-Token (double submit)
        samesite="lax",
    )


def clear_auth_cookies(response: Response, settings: Settings) -> None:
    for name, path in (
        (ACCESS_COOKIE, ACCESS_PATH),
        (REFRESH_COOKIE, REFRESH_PATH),
        (CSRF_COOKIE, CSRF_PATH),
    ):
        response.delete_cookie(name, path=path, secure=settings.COOKIE_SECURE)

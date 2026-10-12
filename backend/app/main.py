"""FastAPI application factory and process lifecycle."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, ClassVar

from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import-untyped]
from fastapi import FastAPI, Request
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.api.errors import install_error_handlers
from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.core.middleware import AccessLogMiddleware
from app.core.security import load_common_passwords
from app.db.client import create_client, get_database
from app.db.migrations import MigrationSummary, apply_migrations
from app.db.seed import seed_demo
from app.repositories.mongo.store import MongoStore
from app.services.mailer import ConsoleMailer, Mailer
from app.services.rate_limit import InMemoryRateLimiter, RateLimiter


class SecurityHeadersMiddleware:
    """Pure ASGI middleware that adds conservative security response headers."""

    _HEADERS: ClassVar[dict[str, str]] = {
        "content-security-policy": (
            "default-src 'self'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
        ),
        "permissions-policy": "camera=(), geolocation=(), microphone=()",
        "referrer-policy": "no-referrer",
        "x-content-type-options": "nosniff",
        "x-frame-options": "DENY",
    }

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        async def send_with_security_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in self._HEADERS.items():
                    headers.setdefault(name, value)
            await send(message)

        await self.app(scope, receive, send_with_security_headers)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize application resources only when the ASGI app starts."""
    setup_logging()
    load_common_passwords()
    settings = get_settings()
    if settings.ENVIRONMENT == "production" and isinstance(app.state.mailer, ConsoleMailer):
        msg = "ConsoleMailer is development-only: configure a real mailer in production"
        raise RuntimeError(msg)
    client = create_client(settings.MONGODB_URI)
    scheduler: AsyncIOScheduler | None = None

    try:
        app.state.settings = settings
        app.state.mongo_client = client
        app.state.database = get_database(client, settings.DATABASE_NAME)
        app.state.store = MongoStore(client, app.state.database)
        app.state.migration_summary = await apply_migrations(client, settings)
        app.state.demo_seeded = await seed_demo(app.state.database, settings)
        scheduler = AsyncIOScheduler()
        scheduler.start()
        app.state.scheduler = scheduler
        yield
    finally:
        if scheduler is not None and scheduler.running:
            scheduler.shutdown(wait=False)
        await client.close()


def _health_response(request: Request) -> dict[str, Any]:
    response: dict[str, Any] = {"status": "ok"}
    settings = request.app.state.settings
    if settings.ENVIRONMENT == "development":
        summary: MigrationSummary = request.app.state.migration_summary
        response["database"] = {
            "replica_set": True,
            "collections_created": summary.collections_created,
            "collections_updated": summary.collections_updated,
            "indexes_created": summary.indexes_created,
        }
    return response


def create_app(*, mailer: Mailer | None = None, rate_limiter: RateLimiter | None = None) -> FastAPI:
    """Build the ASGI application without opening a database connection."""
    application = FastAPI(title="Abaque API", lifespan=lifespan)
    application.state.mailer = mailer if mailer is not None else ConsoleMailer()
    application.state.rate_limiter = (
        rate_limiter if rate_limiter is not None else InMemoryRateLimiter()
    )
    application.add_middleware(SecurityHeadersMiddleware)
    application.add_middleware(AccessLogMiddleware)
    install_error_handlers(application)
    application.include_router(api_router)

    @application.get("/health")
    async def health(request: Request) -> dict[str, Any]:
        return _health_response(request)

    return application


app = create_app()

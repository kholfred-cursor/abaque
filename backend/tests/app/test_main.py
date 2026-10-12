"""Tests for create_app, its lifespan and the /health route."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx
import pytest
from pymongo import AsyncMongoClient

from app.core import config
from app.core.config import Settings
from app.main import create_app


def test_create_app_opens_no_connection() -> None:
    """Building the app and its OpenAPI schema needs no database."""
    schema = create_app().openapi()
    assert "/health" in schema["paths"]
    assert schema["info"]["title"] == "Abaque API"


@pytest.mark.integration
@pytest.mark.parametrize("environment", ["development", "production"])
async def test_lifespan_and_health(
    monkeypatch: pytest.MonkeyPatch,
    mongo_client: AsyncMongoClient[Any],
    make_settings: Callable[..., Settings],
    environment: str,
) -> None:
    """Startup migrates and seeds; /health hides details outside development."""
    base = make_settings()
    overrides: dict[str, Any] = {"ENVIRONMENT": environment, "SEED_DEMO": False}
    if environment == "production":
        overrides["COOKIE_SECURE"] = True
    settings = base.model_copy(update=overrides)
    monkeypatch.setattr("app.main.get_settings", lambda: settings)
    config.get_settings.cache_clear()

    app = create_app()
    try:
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/health")
        body = response.json()
        assert response.status_code == 200
        assert body["status"] == "ok"
        assert ("database" in body) is (environment == "development")
        assert response.headers["x-frame-options"] == "DENY"
        assert response.headers["x-content-type-options"] == "nosniff"
    finally:
        await mongo_client.drop_database(settings.DATABASE_NAME)

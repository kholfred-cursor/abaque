"""Lot 0 exit criterion: on a fresh development stack, the seeded demo admin can log in.

Regression guard for D033: the original demo emails (*@abaque.local) were rejected by the
email validator (.local is a special-use domain), so the demo account could never log in.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx
import pytest
from pymongo import AsyncMongoClient

from app.core.config import Settings
from app.db.migrations import DEMO_ACCOUNT_EMAILS
from app.main import create_app
from tests.api_support import RecordingMailer

pytestmark = pytest.mark.integration


async def test_seeded_demo_admin_can_log_in(
    monkeypatch: pytest.MonkeyPatch,
    mongo_client: AsyncMongoClient[Any],
    make_settings: Callable[..., Settings],
) -> None:
    settings = make_settings(SEED_DEMO=True)
    monkeypatch.setattr("app.main.get_settings", lambda: settings)
    app = create_app(mailer=RecordingMailer())
    try:
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://abaque.test") as c:
                for email in DEMO_ACCOUNT_EMAILS:
                    response = await c.post(
                        "/api/auth/login", json={"email": email, "password": "admin"}
                    )
                    assert response.status_code == 200, response.text
                    body = response.json()
                    assert body["email_verified"] is True
                    assert body["organization"]["name"] in {"Démo", "Autre"}
    finally:
        await mongo_client.drop_database(settings.DATABASE_NAME)

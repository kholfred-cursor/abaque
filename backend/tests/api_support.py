"""Shared HTTP test support: running app, migrated database, owner account, recording mailer.

Registered for every test via pytest_plugins in tests/conftest.py.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from pymongo import AsyncMongoClient

from app.core.config import Settings
from app.core.security import hash_password
from app.domain.models import AdminCreate, Organization, OrganizationCreate
from app.main import create_app
from app.repositories.mongo.organizations import OrganizationProvisioningRepository
from app.services.rate_limit import InMemoryRateLimiter

PASSWORD = "Correct-Horse-Battery-42!"
BASE_URL = "http://abaque.test"


class RecordingMailer:
    """Captures outgoing emails so tests can follow the links they contain."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str, dict[str, str]]] = []

    async def send(self, to: str, template: str, context: dict[str, str]) -> None:
        self.sent.append((to, template, context))

    def last_token(self, template: str) -> str:
        link = next(c["link"] for _, t, c in reversed(self.sent) if t == template)
        return link.split("token=", 1)[1]


@dataclass
class Api:
    client: httpx.AsyncClient
    app: FastAPI
    settings: Settings
    organization: Organization
    owner_email: str
    owner_id: str
    mailer: RecordingMailer

    def cookie_header(self, **cookies: str) -> dict[str, str]:
        return {"Cookie": "; ".join(f"{k}={v}" for k, v in cookies.items())}

    async def login(self, email: str | None = None, password: str = PASSWORD) -> httpx.Response:
        return await self.client.post(
            "/api/auth/login", json={"email": email or self.owner_email, "password": password}
        )

    async def add_tenant(self, slug: str) -> tuple[Organization, str]:
        org, owner = await OrganizationProvisioningRepository(
            self.app.state.database, self.app.state.mongo_client
        ).create_with_owner(
            OrganizationCreate(name=slug.title(), slug=slug),
            AdminCreate(
                email=f"owner@{slug}.example",
                password_hash=hash_password(PASSWORD),
                email_verified=True,
            ),
        )
        return org, owner.email


@pytest_asyncio.fixture
async def api(
    monkeypatch: pytest.MonkeyPatch,
    mongo_client: AsyncMongoClient[Any],
    make_settings: Callable[..., Settings],
) -> AsyncIterator[Api]:
    settings = make_settings()
    monkeypatch.setattr("app.main.get_settings", lambda: settings)
    mailer = RecordingMailer()
    app = create_app(rate_limiter=InMemoryRateLimiter(), mailer=mailer)
    try:
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app, client=("203.0.113.7", 50000))
            async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as client:
                api = Api(client, app, settings, None, "", "", mailer)  # type: ignore[arg-type]
                org, email = await api.add_tenant("alpha")
                owner = await app.state.store.admin_auth().find_by_email(email)
                assert owner is not None
                api.organization, api.owner_email, api.owner_id = org, email, owner.id
                yield api
    finally:
        await mongo_client.drop_database(settings.DATABASE_NAME)

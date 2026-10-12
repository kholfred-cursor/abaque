"""Shared settings and MongoDB replica-set fixtures for backend tests."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio
from hypothesis import settings as hypothesis_settings
from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

from app.core.config import Settings
from app.db.client import get_database
from app.db.migrations import apply_migrations

pytest_plugins = ["tests.api_support"]

hypothesis_settings.register_profile("ci", max_examples=500, deadline=None)
hypothesis_settings.register_profile("dev", max_examples=50)
hypothesis_settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "dev"))


@dataclass(frozen=True)
class MigratedDatabase:
    """A disposable test database paired with the settings used to migrate it."""

    database: AsyncDatabase[Any]
    settings: Settings


@pytest.fixture(scope="session")
def mongodb_test_uri() -> str:
    """Return the explicitly configured URI of the test replica set."""
    uri = os.environ.get("MONGODB_TEST_URI")
    if uri is None:
        pytest.fail("MONGODB_TEST_URI must point to the MongoDB replica set used for tests")
    return uri


@pytest_asyncio.fixture(scope="session")
async def mongo_client(mongodb_test_uri: str) -> AsyncIterator[AsyncMongoClient[Any]]:
    """Connect once to the test-only MongoDB replica set with test commands enabled."""
    client: AsyncMongoClient[Any] = AsyncMongoClient(
        mongodb_test_uri,
        uuidRepresentation="standard",
        tz_aware=True,
        w="majority",
        readConcernLevel="majority",
        retryWrites=True,
    )
    hello = await client.admin.command("hello")
    if "setName" not in hello:
        await client.close()
        pytest.fail("MongoDB test instance must run as a replica set")

    try:
        await client.admin.command({"configureFailPoint": "failCommand", "mode": "off"})
    except Exception as exc:
        await client.close()
        pytest.fail(f"MongoDB test commands must be enabled: {exc}")

    try:
        yield client
    finally:
        await client.close()


@pytest.fixture
def make_settings(mongodb_test_uri: str) -> Callable[..., Settings]:
    """Build valid, distinct settings values suitable for a disposable test database."""
    database_name = f"abaque_test_{uuid4().hex}"
    base_values: dict[str, Any] = {
        "MONGODB_URI": mongodb_test_uri,
        "DATABASE_NAME": database_name,
        "JWT_SECRET": "j" * 32,
        "CREDENTIAL_HMAC_KEY": "h" * 32,
        "IP_HASH_SALT": "s" * 16,
    }

    def factory(**overrides: Any) -> Settings:
        values = {**base_values, **overrides}
        return Settings(**values)

    return factory


@pytest_asyncio.fixture
async def migrated_database(
    mongo_client: AsyncMongoClient[Any],
    make_settings: Callable[..., Settings],
) -> AsyncIterator[MigratedDatabase]:
    """Create a fresh migrated database, then remove it at the end of the test."""
    settings = make_settings()
    database = get_database(mongo_client, settings.DATABASE_NAME)
    await mongo_client.drop_database(settings.DATABASE_NAME)
    await apply_migrations(mongo_client, settings)
    try:
        yield MigratedDatabase(database=database, settings=settings)
    finally:
        await mongo_client.drop_database(settings.DATABASE_NAME)

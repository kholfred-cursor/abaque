"""Integration tests for idempotent and guarded MongoDB migrations."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from pymongo import AsyncMongoClient

from app.core.config import Settings
from app.db.client import get_database
from app.db.migrations import apply_migrations
from app.db.schemas import ALL_SCHEMAS
from tests.conftest import MigratedDatabase
from tests.db.factories import valid_document


@pytest.mark.integration
async def test_migrations_are_idempotent(
    mongo_client: AsyncMongoClient[dict[str, Any]], make_settings: Callable[..., Settings]
) -> None:
    """A second migration pass does not create or modify any collection."""
    settings = make_settings()
    try:
        await mongo_client.drop_database(settings.DATABASE_NAME)
        first = await apply_migrations(mongo_client, settings)
        second = await apply_migrations(mongo_client, settings)

        assert first.collections_created == len(ALL_SCHEMAS)
        assert first.collections_updated == 0
        assert second.collections_created == 0
        assert second.collections_updated == 0
        assert second.indexes_created == 0
    finally:
        await mongo_client.drop_database(settings.DATABASE_NAME)


@pytest.mark.integration
async def test_migrations_fail_when_a_named_index_conflicts(
    mongo_client: AsyncMongoClient[dict[str, Any]], make_settings: Callable[..., Settings]
) -> None:
    """A differently defined stable index name is never silently replaced."""
    settings = make_settings()
    database = get_database(mongo_client, settings.DATABASE_NAME)
    try:
        await mongo_client.drop_database(settings.DATABASE_NAME)
        await database.create_collection("organizations")
        await database["organizations"].create_index([("name", 1)], name="uq_organizations_slug")

        with pytest.raises(RuntimeError, match="Index conflict"):
            await apply_migrations(mongo_client, settings)
    finally:
        await mongo_client.drop_database(settings.DATABASE_NAME)


@pytest.mark.integration
async def test_open_version_rejects_credential_key_rotation(
    migrated_database: MigratedDatabase,
    mongo_client: AsyncMongoClient[dict[str, Any]],
) -> None:
    """An open version bound to another key blocks subsequent startup."""
    version = valid_document("versions", ALL_SCHEMAS["versions"])
    version["status"] = "open"
    version["credential_key_id"] = "f" * 16
    assert version["credential_key_id"] != migrated_database.settings.credential_key_id
    await migrated_database.database["versions"].insert_one(version)

    with pytest.raises(RuntimeError, match="rotation de CREDENTIAL_HMAC_KEY interdite"):
        await apply_migrations(mongo_client, migrated_database.settings)


@pytest.mark.integration
async def test_open_version_without_a_bound_key_does_not_block_startup(
    migrated_database: MigratedDatabase,
    mongo_client: AsyncMongoClient[dict[str, Any]],
) -> None:
    """An explicitly null key identifier is compatible with the current migration guard."""
    version = valid_document("versions", ALL_SCHEMAS["versions"])
    version["status"] = "open"
    version["credential_key_id"] = None
    await migrated_database.database["versions"].insert_one(version)

    summary = await apply_migrations(mongo_client, migrated_database.settings)

    assert summary.collections_created == 0
    assert summary.collections_updated == 0


@pytest.mark.integration
async def test_production_rejects_demo_accounts(
    migrated_database: MigratedDatabase,
    mongo_client: AsyncMongoClient[dict[str, Any]],
    make_settings: Callable[..., Settings],
) -> None:
    """Demo accounts cannot remain when production migrations run."""
    admin = valid_document("admins", ALL_SCHEMAS["admins"])
    admin["email"] = "admin@demo.example.com"
    await migrated_database.database["admins"].insert_one(admin)
    production_settings = make_settings(
        ENVIRONMENT="production",
        COOKIE_SECURE=True,
        MONGODB_URI="mongodb://production-test:27017/abaque?replicaSet=rs0",
    )

    with pytest.raises(RuntimeError, match="Demo accounts are forbidden in production"):
        await apply_migrations(mongo_client, production_settings)

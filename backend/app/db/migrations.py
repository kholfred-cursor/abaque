"""Idempotent MongoDB schema, index, and startup safety migrations."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from pymongo import AsyncMongoClient
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.asynchronous.database import AsyncDatabase

from app.core.config import Settings
from app.db.client import get_database, verify_replica_set
from app.db.indexes import INDEXES, IndexDefinition
from app.db.schemas import ALL_SCHEMAS

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MigrationSummary:
    """Non-sensitive summary retained for health diagnostics in development."""

    collections_created: int
    collections_updated: int
    indexes_created: int


async def _ensure_collection(
    database: AsyncDatabase[Any],
    collection_name: str,
    schema: dict[str, Any],
    existing_options: dict[str, dict[str, Any]],
) -> str:
    """Create or align one collection validator. Returns "created", "updated" or "unchanged"."""
    validator = {"$jsonSchema": schema}
    if collection_name not in existing_options:
        await database.create_collection(
            collection_name,
            validator=validator,
            validationLevel="strict",
            validationAction="error",
        )
        return "created"

    options = existing_options[collection_name]
    if (
        options.get("validator") == validator
        and options.get("validationLevel") == "strict"
        and options.get("validationAction") == "error"
    ):
        return "unchanged"

    await database.command(
        {
            "collMod": collection_name,
            "validator": validator,
            "validationLevel": "strict",
            "validationAction": "error",
        }
    )
    return "updated"


async def _collection_options(database: AsyncDatabase[Any]) -> dict[str, dict[str, Any]]:
    cursor = await database.list_collections()
    collections = await cursor.to_list(None)
    return {str(info["name"]): dict(info.get("options", {})) for info in collections}


def _index_matches(existing: dict[str, Any], definition: IndexDefinition) -> bool:
    existing_key = tuple((field, direction) for field, direction in existing["key"].items())
    if existing_key != definition.keys:
        return False
    if bool(existing.get("unique", False)) != definition.unique:
        return False
    if existing.get("partialFilterExpression") != definition.partial_filter:
        return False
    return existing.get("expireAfterSeconds") == definition.expire_after_seconds


async def _indexes_by_name(collection: AsyncCollection[Any]) -> dict[str, dict[str, Any]]:
    cursor = await collection.list_indexes()
    indexes = await cursor.to_list(None)
    return {str(index["name"]): dict(index) for index in indexes}


async def _ensure_indexes(database: AsyncDatabase[Any]) -> int:
    created = 0
    indexes_by_collection: dict[str, dict[str, dict[str, Any]]] = {}

    for definition in INDEXES:
        existing = indexes_by_collection.get(definition.collection)
        if existing is None:
            existing = await _indexes_by_name(database[definition.collection])
            indexes_by_collection[definition.collection] = existing

        found = existing.get(definition.name)
        if found is not None:
            if not _index_matches(found, definition):
                msg = (
                    f"Index conflict for '{definition.collection}.{definition.name}': "
                    "the existing index definition differs from the required definition"
                )
                raise RuntimeError(msg)
            continue

        await database[definition.collection].create_index(definition.keys, **definition.options())
        created += 1

    return created


async def _configure_profiler(database: AsyncDatabase[Any], settings: Settings) -> None:
    await database.command({"profile": 0, "slowms": settings.MONGO_SLOWMS})


async def _assert_key_rotation_is_safe(database: AsyncDatabase[Any], settings: Settings) -> None:
    open_version = await database["versions"].find_one(
        {"status": "open", "credential_key_id": {"$nin": [None, settings.credential_key_id]}},
        {"_id": 1},
    )
    if open_version is not None:
        msg = "rotation de CREDENTIAL_HMAC_KEY interdite tant qu'une version est ouverte"
        raise RuntimeError(msg)


async def _assert_no_demo_accounts(database: AsyncDatabase[Any]) -> None:
    demo_account = await database["admins"].find_one(
        {"email": {"$in": ["admin@abaque.local", "other@abaque.local"]}},
        {"_id": 1},
    )
    if demo_account is not None:
        raise RuntimeError("Demo accounts are forbidden in production")


async def apply_migrations(client: AsyncMongoClient[Any], settings: Settings) -> MigrationSummary:
    """Apply database safety settings, validators, and indexes without deletion."""
    await verify_replica_set(client)
    database = get_database(client, settings.DATABASE_NAME)
    existing_options = await _collection_options(database)

    collections_created = 0
    collections_updated = 0
    for collection_name, schema in ALL_SCHEMAS.items():
        outcome = await _ensure_collection(database, collection_name, schema, existing_options)
        if outcome == "created":
            collections_created += 1
        elif outcome == "updated":
            collections_updated += 1

    indexes_created = await _ensure_indexes(database)
    await _configure_profiler(database, settings)
    await _assert_key_rotation_is_safe(database, settings)
    if settings.ENVIRONMENT == "production":
        await _assert_no_demo_accounts(database)

    summary = MigrationSummary(
        collections_created=collections_created,
        collections_updated=collections_updated,
        indexes_created=indexes_created,
    )
    logger.info(
        "Database migrations complete: %d collections created, %d collections updated, "
        "%d indexes created",
        summary.collections_created,
        summary.collections_updated,
        summary.indexes_created,
    )
    return summary

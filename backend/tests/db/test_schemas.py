"""Integration tests proving that MongoDB itself enforces every validator."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest
from pymongo.errors import WriteError

from app.db.schemas import ALL_SCHEMAS, VOTE_DOMAIN
from tests.conftest import MigratedDatabase
from tests.db.factories import valid_document


async def _valid_base(migrated_database: MigratedDatabase, collection_name: str) -> dict[str, Any]:
    """Return a document proven valid by MongoDB, so a later rejection has one cause only."""
    document = valid_document(collection_name, ALL_SCHEMAS[collection_name])
    collection = migrated_database.database[collection_name]
    await collection.insert_one(deepcopy(document))
    await collection.delete_one({"_id": document["_id"]})
    return document


@pytest.mark.integration
@pytest.mark.parametrize("collection_name", sorted(ALL_SCHEMAS))
async def test_each_schema_accepts_its_valid_document_and_rejects_extra_fields(
    migrated_database: MigratedDatabase, collection_name: str
) -> None:
    """Every declared collection accepts its minimal valid document and rejects an extra key."""
    collection = migrated_database.database[collection_name]
    valid = valid_document(collection_name, ALL_SCHEMAS[collection_name])
    invalid = deepcopy(valid)
    invalid["unexpected_field"] = "must-be-rejected"

    with pytest.raises(WriteError) as error:
        await collection.insert_one(invalid)
    assert error.value.code == 121

    await collection.insert_one(valid)


@pytest.mark.integration
@pytest.mark.parametrize("collection_name", sorted(VOTE_DOMAIN))
@pytest.mark.parametrize(
    "forbidden_field",
    ["credential_fingerprint", "participant_id", "email", "token", "created_at", "updated_at"],
)
async def test_vote_domain_rejects_identity_and_audit_fields(
    migrated_database: MigratedDatabase, collection_name: str, forbidden_field: str
) -> None:
    """Vote-domain validators prohibit fields that could undermine anonymity."""
    document = await _valid_base(migrated_database, collection_name)
    document[forbidden_field] = "forbidden"

    with pytest.raises(WriteError) as error:
        await migrated_database.database[collection_name].insert_one(document)
    assert error.value.code == 121


@pytest.mark.integration
async def test_ballots_reject_a_vote_date_containing_a_time(
    migrated_database: MigratedDatabase,
) -> None:
    """Vote-domain dates are date-only strings, never datetimes or timestamp strings."""
    ballot = await _valid_base(migrated_database, "ballots")
    ballot["submitted_on"] = "2026-01-02T10:30:00Z"

    with pytest.raises(WriteError) as error:
        await migrated_database.database["ballots"].insert_one(ballot)
    assert error.value.code == 121


@pytest.mark.integration
@pytest.mark.parametrize("collection_name", sorted(VOTE_DOMAIN))
async def test_vote_domain_rejects_non_uuid_v4_ids(
    migrated_database: MigratedDatabase, collection_name: str
) -> None:
    """Anonymous vote-domain records require UUID v4 identifiers."""
    document = await _valid_base(migrated_database, collection_name)
    document["_id"] = "00000000-0000-1000-8000-000000000000"

    with pytest.raises(WriteError) as error:
        await migrated_database.database[collection_name].insert_one(document)
    assert error.value.code == 121

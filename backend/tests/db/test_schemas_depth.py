"""Block 6: validators reject unknown fields at EVERY level, not only at the root."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest
from pymongo.errors import WriteError

from app.db.schemas import ALL_SCHEMAS
from tests.conftest import MigratedDatabase
from tests.db.factories import _valid_value, valid_document

pytestmark = pytest.mark.integration


def _nested_cases() -> list[tuple[str, str, str]]:
    """(collection, field, kind) for every nested object or array of objects in a schema."""
    cases = []
    for collection, schema in ALL_SCHEMAS.items():
        for field, sub in schema["properties"].items():
            types = sub.get("bsonType")
            types = types if isinstance(types, list) else [types]
            if "object" in types and ("properties" in sub or "patternProperties" in sub):
                cases.append((collection, field, "object"))
            items = sub.get("items")
            if "array" in types and isinstance(items, dict) and items.get("bsonType") == "object":
                cases.append((collection, field, "array"))
    return cases


NESTED = _nested_cases()


def test_the_depth_scan_finds_the_known_nested_structures() -> None:
    """Guard against a vacuous pass if the scan stopped finding anything."""
    found = {(c, f) for c, f, _ in NESTED}
    assert {("organizations", "entitlements"), ("organizations", "usage")} <= found
    assert ("segment_questions", "options") in found


async def _insert(db: MigratedDatabase, collection: str, document: dict[str, Any]) -> None:
    await db.database[collection].insert_one(document)
    await db.database[collection].delete_one({"_id": document["_id"]})


@pytest.mark.parametrize(("collection", "field", "kind"), NESTED, ids=lambda v: str(v))
async def test_unknown_key_inside_nested_structure_is_rejected(
    migrated_database: MigratedDatabase, collection: str, field: str, kind: str
) -> None:
    schema = ALL_SCHEMAS[collection]
    sub = schema["properties"][field]
    base = valid_document(collection, schema)

    if kind == "array":
        item = _valid_value(collection, field, sub["items"])
        valid = {**deepcopy(base), field: [item]}
        invalid = {**deepcopy(base), field: [{**item, "unexpected": "x"}]}
    elif "patternProperties" in sub:  # e.g. usage.{YYYY-MM}: only pattern keys allowed
        valid = {**deepcopy(base), field: {"2026-10": {}}}
        invalid = {**deepcopy(base), field: {"not-a-month": {}}}
    else:
        nested = _valid_value(collection, field, sub)
        valid = {**deepcopy(base), field: nested}
        invalid = {**deepcopy(base), field: {**nested, "unexpected": "x"}}

    await _insert(migrated_database, collection, valid)  # proves the only fault is the extra key
    with pytest.raises(WriteError) as error:
        await migrated_database.database[collection].insert_one(invalid)
    assert error.value.code == 121


async def test_usage_month_object_rejects_unknown_counters(
    migrated_database: MigratedDatabase,
) -> None:
    base = valid_document("organizations", ALL_SCHEMAS["organizations"])
    await _insert(
        migrated_database, "organizations", {**base, "usage": {"2026-10": {"ballots": 3}}}
    )
    with pytest.raises(WriteError):
        await migrated_database.database["organizations"].insert_one(
            {**base, "usage": {"2026-10": {"ballots": 3, "secret": 1}}}
        )


@pytest.mark.parametrize("threshold", [0, 1, 2])
async def test_anonymity_threshold_below_three_is_rejected(
    migrated_database: MigratedDatabase, threshold: int
) -> None:
    base = valid_document("evaluations", ALL_SCHEMAS["evaluations"])
    assert base["anonymity_threshold"] >= 3
    await _insert(migrated_database, "evaluations", deepcopy(base))
    with pytest.raises(WriteError):
        await migrated_database.database["evaluations"].insert_one(
            {**base, "anonymity_threshold": threshold}
        )

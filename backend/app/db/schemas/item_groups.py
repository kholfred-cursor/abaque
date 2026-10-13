"""$jsonSchema for the item_groups collection."""

from __future__ import annotations

from typing import Any

SCHEMA: dict[str, Any] = {
    "bsonType": "object",
    "required": ["_id", "organization_id", "version_id", "name", "position"],
    "additionalProperties": False,
    "properties": {
        "_id": {"bsonType": "objectId"},
        "organization_id": {"bsonType": "objectId"},
        "version_id": {"bsonType": "objectId"},
        "name": {"bsonType": "string", "minLength": 1, "maxLength": 200},
        "position": {"bsonType": "int", "minimum": 0},
    },
}

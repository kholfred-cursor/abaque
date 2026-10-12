"""$jsonSchema for the items collection."""

from __future__ import annotations

from typing import Any

SCHEMA: dict[str, Any] = {
    "bsonType": "object",
    "required": ["_id", "organization_id", "version_id", "group_id", "short_name", "statement", "position"],
    "additionalProperties": False,
    "properties": {
        "_id": {"bsonType": "objectId"},
        "organization_id": {"bsonType": "objectId"},
        "version_id": {"bsonType": "objectId"},
        "group_id": {"bsonType": "objectId"},
        "short_name": {"bsonType": "string", "minLength": 1, "maxLength": 50},
        "statement": {"bsonType": "string", "minLength": 1, "maxLength": 2000},
        "position": {"bsonType": "int", "minimum": 0},
    },
}

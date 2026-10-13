"""$jsonSchema for the glossary collection."""

from __future__ import annotations

from typing import Any

SCHEMA: dict[str, Any] = {
    "bsonType": "object",
    "required": ["_id", "organization_id", "version_id", "key", "value"],
    "additionalProperties": False,
    "properties": {
        "_id": {"bsonType": "objectId"},
        "organization_id": {"bsonType": "objectId"},
        "version_id": {"bsonType": "objectId"},
        "key": {"bsonType": "string", "minLength": 1, "maxLength": 50},
        "value": {"bsonType": "string", "minLength": 1, "maxLength": 200},
    },
}

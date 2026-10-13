"""$jsonSchema for the general_questions collection."""

from __future__ import annotations

from typing import Any

SCHEMA: dict[str, Any] = {
    "bsonType": "object",
    "required": ["_id", "organization_id", "version_id", "text", "position"],
    "additionalProperties": False,
    "properties": {
        "_id": {"bsonType": "objectId"},
        "organization_id": {"bsonType": "objectId"},
        "version_id": {"bsonType": "objectId"},
        "text": {"bsonType": "string", "minLength": 1, "maxLength": 1000},
        "position": {"bsonType": "int", "minimum": 0},
    },
}

"""$jsonSchema for the color_labels collection."""

from __future__ import annotations

from typing import Any

from app.db.schemas._patterns import COLOR_KEYS

SCHEMA: dict[str, Any] = {
    "bsonType": "object",
    "required": ["_id", "organization_id", "version_id", "color_key", "label"],
    "additionalProperties": False,
    "properties": {
        "_id": {"bsonType": "objectId"},
        "organization_id": {"bsonType": "objectId"},
        "version_id": {"bsonType": "objectId"},
        "color_key": {"bsonType": "string", "enum": COLOR_KEYS},
        "label": {"bsonType": "string", "minLength": 1, "maxLength": 100},
    },
}

"""$jsonSchema for the votes collection (vote domain)."""

from __future__ import annotations

from typing import Any

from app.db.schemas._patterns import COLOR_KEYS, UUID_V4

SCHEMA: dict[str, Any] = {
    "bsonType": "object",
    "required": ["_id", "organization_id", "ballot_id", "item_id", "color_key", "comment_status"],
    "additionalProperties": False,
    "properties": {
        "_id": {"bsonType": "string", "pattern": UUID_V4},
        "organization_id": {"bsonType": "objectId"},
        "ballot_id": {"bsonType": "string", "pattern": UUID_V4},
        "item_id": {"bsonType": "objectId"},
        "color_key": {"bsonType": "string", "enum": COLOR_KEYS},
        "comment": {"bsonType": ["string", "null"], "maxLength": 5000},
        "comment_status": {"bsonType": "string", "enum": ["published", "hidden", "flagged"]},
    },
}

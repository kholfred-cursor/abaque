"""$jsonSchema for the segment_answers collection (vote domain)."""

from __future__ import annotations

from typing import Any

from app.db.schemas._patterns import UUID_V4

SCHEMA: dict[str, Any] = {
    "bsonType": "object",
    "required": ["_id", "organization_id", "ballot_id", "question_id"],
    "additionalProperties": False,
    "properties": {
        "_id": {"bsonType": "string", "pattern": UUID_V4},
        "organization_id": {"bsonType": "objectId"},
        "ballot_id": {"bsonType": "string", "pattern": UUID_V4},
        "question_id": {"bsonType": "objectId"},
        "option_ids": {
            "bsonType": "array",
            "minItems": 1,
            "items": {"bsonType": "string", "minLength": 1, "maxLength": 50},
        },
        "bucket": {"bsonType": "string", "minLength": 1, "maxLength": 50},
    },
    # exactly one of option_ids / bucket (never a raw numeric value)
    "oneOf": [
        {"required": ["option_ids"], "not": {"required": ["bucket"]}},
        {"required": ["bucket"], "not": {"required": ["option_ids"]}},
    ],
}

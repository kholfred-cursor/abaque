"""$jsonSchema for the segment_questions collection."""

from __future__ import annotations

from typing import Any

SCHEMA: dict[str, Any] = {
    "bsonType": "object",
    "required": ["_id", "organization_id", "version_id", "text", "type", "required", "position"],
    "additionalProperties": False,
    "properties": {
        "_id": {"bsonType": "objectId"},
        "organization_id": {"bsonType": "objectId"},
        "version_id": {"bsonType": "objectId"},
        "group_id": {"bsonType": ["objectId", "null"]},
        "text": {"bsonType": "string", "minLength": 1, "maxLength": 500},
        # no "email" type (D007)
        "type": {"bsonType": "string", "enum": ["single", "multiple", "text", "number"]},
        "options": {
            "bsonType": ["array", "null"],
            "items": {
                "bsonType": "object",
                "required": ["id", "label"],
                "additionalProperties": False,
                "properties": {
                    "id": {"bsonType": "string", "minLength": 1, "maxLength": 50},
                    "label": {"bsonType": "string", "minLength": 1, "maxLength": 200},
                },
            },
        },
        "number_buckets": {
            "bsonType": ["array", "null"],
            "items": {
                "bsonType": "object",
                "required": ["id", "label", "min", "max"],
                "additionalProperties": False,
                "properties": {
                    "id": {"bsonType": "string", "minLength": 1, "maxLength": 50},
                    "label": {"bsonType": "string", "minLength": 1, "maxLength": 200},
                    "min": {"bsonType": ["double", "int", "long", "null"]},
                    "max": {"bsonType": ["double", "int", "long", "null"]},
                },
            },
        },
        "required": {"bsonType": "bool"},
        "position": {"bsonType": "int", "minimum": 0},
    },
}

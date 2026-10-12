"""$jsonSchema for the participants collection (identity domain; no vote timestamp, only has_voted)."""

from __future__ import annotations

from typing import Any

from app.db.schemas._patterns import SHA256_HEX

SCHEMA: dict[str, Any] = {
    "bsonType": "object",
    "required": ["_id", "organization_id", "version_id", "groups", "has_voted", "invited"],
    "additionalProperties": False,
    "properties": {
        "_id": {"bsonType": "objectId"},
        "organization_id": {"bsonType": "objectId"},
        "version_id": {"bsonType": "objectId"},
        # stored normalized (normalize_email)
        "email": {"bsonType": ["string", "null"], "minLength": 3, "maxLength": 254},
        "first_name": {"bsonType": ["string", "null"], "maxLength": 100},
        "last_name": {"bsonType": ["string", "null"], "maxLength": 100},
        "trigram": {"bsonType": ["string", "null"], "maxLength": 10},
        "groups": {
            "bsonType": "array",
            "items": {"bsonType": "string", "minLength": 1, "maxLength": 100},
        },
        "token_hash": {"bsonType": ["string", "null"], "pattern": SHA256_HEX},
        "has_voted": {"bsonType": "bool"},
        "invited": {"bsonType": "bool"},
    },
}

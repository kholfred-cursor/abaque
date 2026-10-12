"""$jsonSchema for the admin_sessions collection."""

from __future__ import annotations

from typing import Any

from app.db.schemas._patterns import SHA256_HEX

SCHEMA: dict[str, Any] = {
    "bsonType": "object",
    "required": ["_id", "admin_id", "token_hash", "expires_at", "created_at"],
    "additionalProperties": False,
    "properties": {
        "_id": {"bsonType": "objectId"},
        "admin_id": {"bsonType": "objectId"},
        "token_hash": {"bsonType": "string", "pattern": SHA256_HEX},
        "expires_at": {"bsonType": "date"},
        "created_at": {"bsonType": "date"},
        "last_used_at": {"bsonType": ["date", "null"]},
        "revoked_at": {"bsonType": ["date", "null"]},
        "consumed_at": {"bsonType": ["date", "null"]},
        "user_agent_hint": {"bsonType": ["string", "null"], "maxLength": 200},
    },
}

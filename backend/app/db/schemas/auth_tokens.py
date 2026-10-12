"""$jsonSchema for the auth_tokens collection (admin email verification and password reset; TTL on expires_at)."""

from __future__ import annotations

from typing import Any

from app.db.schemas._patterns import SHA256_HEX

SCHEMA: dict[str, Any] = {
    "bsonType": "object",
    "required": ["_id", "admin_id", "purpose", "token_hash", "expires_at"],
    "additionalProperties": False,
    "properties": {
        "_id": {"bsonType": "objectId"},
        "admin_id": {"bsonType": "objectId"},
        # magic_link_admin: reserved, unused in the MVP (D025)
        "purpose": {
            "bsonType": "string",
            "enum": ["verify_email", "reset_password", "magic_link_admin"],
        },
        "token_hash": {"bsonType": "string", "pattern": SHA256_HEX},
        "expires_at": {"bsonType": "date"},
        "used_at": {"bsonType": ["date", "null"]},
    },
}

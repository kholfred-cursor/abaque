"""$jsonSchema for the admins collection."""

from __future__ import annotations

from typing import Any

from app.db.schemas._patterns import ARGON2ID

SCHEMA: dict[str, Any] = {
    "bsonType": "object",
    "required": ["_id", "email", "email_verified", "password_hash", "role", "created_at"],
    "additionalProperties": False,
    "properties": {
        "_id": {"bsonType": "objectId"},
        # null / absent for the platform superadmin
        "organization_id": {"bsonType": ["objectId", "null"]},
        "email": {"bsonType": "string", "minLength": 3, "maxLength": 254},
        "email_verified": {"bsonType": "bool"},
        "password_hash": {"bsonType": "string", "pattern": ARGON2ID},
        "role": {"bsonType": "string", "enum": ["owner", "animator", "superadmin"]},
        "totp_secret_enc": {"bsonType": ["string", "null"], "maxLength": 500},
        "created_at": {"bsonType": "date"},
    },
}

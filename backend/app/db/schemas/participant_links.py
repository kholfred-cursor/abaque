"""$jsonSchema for the participant_links collection.

Identity domain: consumed by deletion, no used_at.
"""

from __future__ import annotations

from typing import Any

from app.db.schemas._patterns import SHA256_HEX

SCHEMA: dict[str, Any] = {
    "bsonType": "object",
    "required": [
        "_id",
        "organization_id",
        "version_id",
        "email_normalized",
        "token_hash",
        "expires_at",
    ],
    "additionalProperties": False,
    "properties": {
        "_id": {"bsonType": "objectId"},
        "organization_id": {"bsonType": "objectId"},
        "version_id": {"bsonType": "objectId"},
        "email_normalized": {"bsonType": "string", "minLength": 3, "maxLength": 254},
        "token_hash": {"bsonType": "string", "pattern": SHA256_HEX},
        # date type required by the TTL index (exception documented in D016)
        "expires_at": {"bsonType": "date"},
    },
}

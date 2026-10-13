"""$jsonSchema for the credential_uses collection.

Identity domain: consumption marker only (no ballot_id, no hour).
"""

from __future__ import annotations

from typing import Any

from app.db.schemas._patterns import DAY, KEY_ID, SHA256_HEX

SCHEMA: dict[str, Any] = {
    "bsonType": "object",
    "required": [
        "_id",
        "organization_id",
        "version_id",
        "credential_fingerprint",
        "key_id",
        "consumed_on",
    ],
    "additionalProperties": False,
    "properties": {
        "_id": {"bsonType": "objectId"},
        "organization_id": {"bsonType": "objectId"},
        "version_id": {"bsonType": "objectId"},
        "credential_fingerprint": {"bsonType": "string", "pattern": SHA256_HEX},
        "key_id": {"bsonType": "string", "pattern": KEY_ID},
        "consumed_on": {"bsonType": "string", "pattern": DAY},
    },
}

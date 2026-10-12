"""$jsonSchema for the email_logs collection (identity domain)."""

from __future__ import annotations

from typing import Any

from app.db.schemas._patterns import DAY

SCHEMA: dict[str, Any] = {
    "bsonType": "object",
    "required": [
        "_id", "organization_id", "version_id", "participant_id", "kind", "sent_on", "status",
    ],
    "additionalProperties": False,
    "properties": {
        "_id": {"bsonType": "objectId"},
        "organization_id": {"bsonType": "objectId"},
        "version_id": {"bsonType": "objectId"},
        "participant_id": {"bsonType": "objectId"},
        "kind": {"bsonType": "string", "enum": ["invitation", "reminder", "magic_link"]},
        "sent_on": {"bsonType": "string", "pattern": DAY},
        "status": {"bsonType": "string", "enum": ["sent", "failed", "bounced"]},
    },
}

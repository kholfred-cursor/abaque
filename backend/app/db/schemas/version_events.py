"""$jsonSchema for the version_events collection."""

from __future__ import annotations

from typing import Any

SCHEMA: dict[str, Any] = {
    "bsonType": "object",
    "required": ["_id", "organization_id", "version_id", "kind", "at"],
    "additionalProperties": False,
    "properties": {
        "_id": {"bsonType": "objectId"},
        "organization_id": {"bsonType": "objectId"},
        "version_id": {"bsonType": "objectId"},
        # export granularity accepted (D026)
        "kind": {
            "bsonType": "string",
            "enum": [
                "opened", "closed", "reopened", "archived", "reminder_sent", "purged",
                "export_aggregated", "export_ballots", "export_texts", "export_pdf",
            ],
        },
        "at": {"bsonType": "date"},
        "admin_id": {"bsonType": ["objectId", "null"]},
    },
}

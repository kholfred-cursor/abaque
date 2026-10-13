"""$jsonSchema for the ballots collection.

Vote domain: UUID v4 _id, day-only date, no identity field.
"""

from __future__ import annotations

from typing import Any

from app.db.schemas._patterns import DAY, UUID_V4

SCHEMA: dict[str, Any] = {
    "bsonType": "object",
    "required": ["_id", "organization_id", "version_id", "submitted_on", "groups", "rand_key"],
    "additionalProperties": False,
    "properties": {
        "_id": {"bsonType": "string", "pattern": UUID_V4},
        "organization_id": {"bsonType": "objectId"},
        "version_id": {"bsonType": "objectId"},
        "submitted_on": {"bsonType": "string", "pattern": DAY},
        "groups": {
            "bsonType": "array",
            "items": {"bsonType": "string", "minLength": 1, "maxLength": 100},
        },
        "rand_key": {"bsonType": "double"},
    },
}

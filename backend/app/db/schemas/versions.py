"""$jsonSchema for the versions collection."""

from __future__ import annotations

from typing import Any

from app.db.schemas._patterns import KEY_ID

SCHEMA: dict[str, Any] = {
    "bsonType": "object",
    "required": [
        "_id",
        "organization_id",
        "evaluation_id",
        "label",
        "status",
        "is_visible",
        "ballot_count",
    ],
    "additionalProperties": False,
    "properties": {
        "_id": {"bsonType": "objectId"},
        "organization_id": {"bsonType": "objectId"},
        "evaluation_id": {"bsonType": "objectId"},
        "label": {"bsonType": "string", "minLength": 1, "maxLength": 100},
        "status": {"bsonType": "string", "enum": ["draft", "open", "closed", "archived"]},
        "is_visible": {"bsonType": "bool"},
        "ballot_count": {"bsonType": "int", "minimum": 0},
        # incremented by every content save: a real write on the version document, so a
        # content save and a first ballot conflict inside MongoDB transactions (lot 1, D038)
        "content_revision": {"bsonType": "int", "minimum": 0},
        # set when the version is opened; used by the key-rotation guard
        "credential_key_id": {"bsonType": ["string", "null"], "pattern": KEY_ID},
        "closed_at": {"bsonType": ["date", "null"]},
        "purge_at": {"bsonType": ["date", "null"]},
    },
}

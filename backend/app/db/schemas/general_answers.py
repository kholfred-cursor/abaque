"""$jsonSchema for the general_answers collection (vote domain)."""

from __future__ import annotations

from typing import Any

from app.db.schemas._patterns import UUID_V4

SCHEMA: dict[str, Any] = {
    "bsonType": "object",
    "required": ["_id", "organization_id", "ballot_id", "question_id", "text", "comment_status"],
    "additionalProperties": False,
    "properties": {
        "_id": {"bsonType": "string", "pattern": UUID_V4},
        "organization_id": {"bsonType": "objectId"},
        "ballot_id": {"bsonType": "string", "pattern": UUID_V4},
        # general question, or segment question of type "text"
        "question_id": {"bsonType": "objectId"},
        "text": {"bsonType": "string", "minLength": 1, "maxLength": 5000},
        "comment_status": {"bsonType": "string", "enum": ["published", "hidden", "flagged"]},
    },
}

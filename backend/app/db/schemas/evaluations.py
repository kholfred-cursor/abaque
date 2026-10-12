"""$jsonSchema for the evaluations collection."""

from __future__ import annotations

from typing import Any

SCHEMA: dict[str, Any] = {
    "bsonType": "object",
    "required": [
        "_id", "organization_id", "admin_id", "title", "participation_mode",
        "slug", "vote_preset", "show_vote_example", "anonymity_threshold", "created_at",
    ],
    "additionalProperties": False,
    "properties": {
        "_id": {"bsonType": "objectId"},
        "organization_id": {"bsonType": "objectId"},
        "admin_id": {"bsonType": "objectId"},
        "title": {"bsonType": "string", "minLength": 1, "maxLength": 300},
        "description": {"bsonType": ["string", "null"], "maxLength": 2000},
        "language": {"bsonType": ["string", "null"], "maxLength": 10},
        "logo_url": {"bsonType": ["string", "null"], "maxLength": 500},
        "participation_mode": {
            "bsonType": "string",
            "enum": ["anonymous", "auth_open", "auth_closed"],
        },
        "allowed_email_domains": {
            "bsonType": ["array", "null"],
            "items": {"bsonType": "string", "minLength": 3, "maxLength": 253},
        },
        "access_code_hash": {"bsonType": ["string", "null"], "maxLength": 200},
        "slug": {"bsonType": "string", "pattern": "^[a-z0-9-]{2,80}$"},
        "vote_preset": {"bsonType": "string", "enum": ["agreement", "score", "custom"]},
        "intro_md": {"bsonType": ["string", "null"], "maxLength": 10000},
        "outro_md": {"bsonType": ["string", "null"], "maxLength": 10000},
        "show_vote_example": {"bsonType": "bool"},
        "anonymity_threshold": {"bsonType": "int", "minimum": 3},
        "settings": {
            "bsonType": "object",
            "additionalProperties": False,
            "properties": {
                "one_item_per_page": {"bsonType": "bool"},
                "comment_required": {"bsonType": "bool"},
                "expected_ballots": {"bsonType": ["int", "null"], "minimum": 0},
            },
        },
        "created_at": {"bsonType": "date"},
    },
}

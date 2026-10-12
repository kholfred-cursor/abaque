"""$jsonSchema for the organizations collection."""

from __future__ import annotations

from typing import Any

from app.db.schemas._patterns import MONTH

SCHEMA: dict[str, Any] = {
    "bsonType": "object",
    "required": [
        "_id",
        "name",
        "slug",
        "plan_code",
        "status",
        "entitlements",
        "usage",
        "created_at",
    ],
    "additionalProperties": False,
    "properties": {
        "_id": {"bsonType": "objectId"},
        "name": {"bsonType": "string", "minLength": 1, "maxLength": 200},
        "slug": {"bsonType": "string", "pattern": "^[a-z0-9-]{2,60}$"},
        "plan_code": {"bsonType": "string", "enum": ["demo", "trial", "standard"]},
        "status": {"bsonType": "string", "enum": ["active", "suspended", "deleted"]},
        "entitlements": {
            "bsonType": "object",
            "additionalProperties": False,
            "properties": {
                "max_active_evaluations": {"bsonType": ["int", "null"], "minimum": 0},
                "max_ballots_per_version": {"bsonType": ["int", "null"], "minimum": 0},
                "max_animators": {"bsonType": ["int", "null"], "minimum": 0},
                "modes_allowed": {
                    "bsonType": "array",
                    "items": {
                        "bsonType": "string",
                        "enum": ["anonymous", "auth_open", "auth_closed"],
                    },
                },
                "pdf_export": {"bsonType": "bool"},
                "csv_export": {"bsonType": "bool"},
                "email_invitations": {"bsonType": "bool"},
                "custom_branding": {"bsonType": "bool"},
                "retention_months": {"bsonType": ["int", "null"], "minimum": 1},
            },
        },
        "usage": {
            "bsonType": "object",
            "additionalProperties": False,
            "patternProperties": {
                MONTH: {
                    "bsonType": "object",
                    "additionalProperties": False,
                    "properties": {
                        "evaluations": {"bsonType": "int", "minimum": 0},
                        "ballots": {"bsonType": "int", "minimum": 0},
                        "emails_sent": {"bsonType": "int", "minimum": 0},
                    },
                },
            },
        },
        "trial_ends_at": {"bsonType": ["date", "null"]},
        "created_at": {"bsonType": "date"},
    },
}

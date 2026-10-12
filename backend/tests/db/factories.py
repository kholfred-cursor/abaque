"""Small document factories used to exercise MongoDB collection validators."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from bson import ObjectId

from app.core.security import hash_password
from app.db.schemas import VOTE_DOMAIN
from app.db.schemas._patterns import ARGON2ID, DAY, KEY_ID, MONTH, SHA256_HEX, UUID_V4


def _valid_string(field_name: str, schema: dict[str, Any]) -> str:
    if "enum" in schema:
        return str(schema["enum"][0])
    pattern = schema.get("pattern")
    if pattern == UUID_V4:
        return str(uuid4())
    if pattern == DAY:
        return "2026-01-02"
    if pattern == MONTH:
        return "2026-01"
    if pattern == SHA256_HEX:
        return "a" * 64
    if pattern == KEY_ID:
        return "a" * 16
    if pattern == ARGON2ID:
        return hash_password("a-valid-test-password")
    if field_name in {"email", "email_normalized"}:
        return "valid@example.test"
    if field_name in {"token_hash", "credential_fingerprint"}:
        return "a" * 64
    if field_name in {"key_id", "credential_key_id"}:
        return "a" * 16
    if field_name in {"submitted_on", "consumed_on", "sent_on"}:
        return "2026-01-02"
    if field_name == "password_hash":
        return hash_password("a-valid-test-password")
    return "valid-value"


def _valid_value(collection_name: str, field_name: str, schema: dict[str, Any]) -> Any:
    if field_name == "_id":
        return str(uuid4()) if collection_name in VOTE_DOMAIN else ObjectId()

    bson_type = schema.get("bsonType")
    if isinstance(bson_type, list):
        bson_type = next(item for item in bson_type if item != "null")
    if bson_type == "objectId":
        return ObjectId()
    if bson_type == "date":
        return datetime.now(UTC)
    if bson_type == "string":
        return _valid_string(field_name, schema)
    if bson_type == "bool":
        return True
    if bson_type == "int":
        return max(0, int(schema.get("minimum", 0)))
    if bson_type == "double":
        return 0.5
    if bson_type == "array":
        return []
    if bson_type == "object":
        return {
            name: _valid_value(collection_name, name, child_schema)
            for name, child_schema in schema.get("properties", {}).items()
            if name in schema.get("required", [])
        }
    msg = f"Unsupported bson type in test document factory: {bson_type}"
    raise ValueError(msg)


def valid_document(collection_name: str, schema: dict[str, Any]) -> dict[str, Any]:
    """Build one valid minimal document for the supplied collection schema."""
    document = {
        field_name: _valid_value(collection_name, field_name, schema["properties"][field_name])
        for field_name in schema["required"]
    }
    if collection_name == "segment_answers":
        document["option_ids"] = ["option-a"]
    return document

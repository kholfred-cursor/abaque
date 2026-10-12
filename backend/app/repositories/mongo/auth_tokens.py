"""Outside-tenant single-use email verification and password reset tokens."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import ReturnDocument
from pymongo.asynchronous.client_session import AsyncClientSession
from pymongo.asynchronous.database import AsyncDatabase

from app.domain.errors import NotFound


def _object_id(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except InvalidId as exc:
        raise NotFound("Resource not found") from exc


class AuthTokenRepository:
    """One active token per administrator and purpose, consumed atomically once."""

    def __init__(self, database: AsyncDatabase[Any]) -> None:
        self.database = database

    @staticmethod
    def _options(session: AsyncClientSession | None) -> dict[str, Any]:
        return {} if session is None else {"session": session}

    async def create(
        self,
        admin_id: str,
        purpose: str,
        token_hash: str,
        expires_at: datetime,
        session: AsyncClientSession | None = None,
    ) -> None:
        options = self._options(session)
        object_id = _object_id(admin_id)
        await self.database["auth_tokens"].delete_many(
            {"admin_id": object_id, "purpose": purpose, "used_at": None}, **options
        )
        await self.database["auth_tokens"].insert_one(
            {
                "_id": ObjectId(),
                "admin_id": object_id,
                "purpose": purpose,
                "token_hash": token_hash,
                "expires_at": expires_at,
                "used_at": None,
            },
            **options,
        )

    async def consume(
        self, token_hash: str, purpose: str, session: AsyncClientSession | None = None
    ) -> str | None:
        document = await self.database["auth_tokens"].find_one_and_update(
            {
                "token_hash": token_hash,
                "purpose": purpose,
                "used_at": None,
                "expires_at": {"$gt": datetime.now(UTC)},
            },
            {"$set": {"used_at": datetime.now(UTC)}},
            return_document=ReturnDocument.BEFORE,
            **self._options(session),
        )
        return None if document is None else str(document["admin_id"])

    async def delete_for_admin(
        self, admin_id: str, purpose: str, session: AsyncClientSession | None = None
    ) -> None:
        await self.database["auth_tokens"].delete_many(
            {"admin_id": _object_id(admin_id), "purpose": purpose}, **self._options(session)
        )

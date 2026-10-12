"""Outside-tenant persistence for rotating administrator refresh sessions."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import AsyncMongoClient, ReturnDocument
from pymongo.asynchronous.client_session import AsyncClientSession
from pymongo.asynchronous.database import AsyncDatabase

from app.db.client import run_in_transaction
from app.domain.errors import NotFound
from app.domain.sessions import (
    ROTATION_GRACE,
    AdminSession,
    ConcurrentRotation,
    SessionReuseDetected,
)


def _object_id(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except InvalidId as exc:
        raise NotFound("Resource not found") from exc


def _session(document: dict[str, Any]) -> AdminSession:
    return AdminSession(
        id=str(document["_id"]),
        admin_id=str(document["admin_id"]),
        token_hash=document["token_hash"],
        expires_at=document["expires_at"],
        created_at=document["created_at"],
        last_used_at=document.get("last_used_at"),
        revoked_at=document.get("revoked_at"),
        consumed_at=document.get("consumed_at"),
        user_agent_hint=document.get("user_agent_hint"),
    )


class AdminSessionRepository:
    """Refresh sessions looked up only by their SHA-256 token hash."""

    def __init__(self, database: AsyncDatabase[Any], client: AsyncMongoClient[Any]) -> None:
        self.database = database
        self.client = client

    @staticmethod
    def _options(session: AsyncClientSession | None) -> dict[str, Any]:
        return {} if session is None else {"session": session}

    async def create(
        self,
        admin_id: str,
        token_hash: str,
        expires_at: datetime,
        session: AsyncClientSession | None = None,
    ) -> AdminSession:
        document: dict[str, Any] = {
            "_id": ObjectId(),
            "admin_id": _object_id(admin_id),
            "token_hash": token_hash,
            "expires_at": expires_at,
            "created_at": datetime.now(UTC),
            "last_used_at": None,
            "revoked_at": None,
            "consumed_at": None,
            "user_agent_hint": None,
        }
        await self.database["admin_sessions"].insert_one(document, **self._options(session))
        return _session(document)

    async def find_by_hash(
        self, token_hash: str, session: AsyncClientSession | None = None
    ) -> AdminSession | None:
        document = await self.database["admin_sessions"].find_one(
            {"token_hash": token_hash}, **self._options(session)
        )
        return None if document is None else _session(dict(document))

    async def revoke(self, token_hash: str, session: AsyncClientSession | None = None) -> None:
        await self.database["admin_sessions"].update_one(
            {"token_hash": token_hash, "revoked_at": None},
            {"$set": {"revoked_at": datetime.now(UTC)}},
            **self._options(session),
        )

    async def revoke_all_for_admin(
        self, admin_id: str, session: AsyncClientSession | None = None
    ) -> int:
        result = await self.database["admin_sessions"].update_many(
            {"admin_id": _object_id(admin_id), "revoked_at": None},
            {"$set": {"revoked_at": datetime.now(UTC)}},
            **self._options(session),
        )
        return result.modified_count

    async def rotate(
        self,
        old_token_hash: str,
        new_token_hash: str,
        expires_at: datetime,
        session: AsyncClientSession | None = None,
    ) -> AdminSession:
        now = datetime.now(UTC)

        async def callback(transaction: AsyncClientSession) -> AdminSession:
            old = await self.database["admin_sessions"].find_one_and_update(
                {
                    "token_hash": old_token_hash,
                    "revoked_at": None,
                    "consumed_at": None,
                    "expires_at": {"$gt": now},
                },
                {"$set": {"consumed_at": now, "last_used_at": now}},
                return_document=ReturnDocument.AFTER,
                session=transaction,
            )
            if old is None:
                previous = await self.database["admin_sessions"].find_one(
                    {"token_hash": old_token_hash}, session=transaction
                )
                if previous is not None and previous.get("consumed_at") is not None:
                    consumed_at = previous["consumed_at"]
                    if consumed_at >= datetime.now(UTC) - ROTATION_GRACE:
                        raise ConcurrentRotation
                    raise SessionReuseDetected(str(previous["admin_id"]))
                raise NotFound("Resource not found")
            return await self.create(
                str(old["admin_id"]), new_token_hash, expires_at, session=transaction
            )

        try:
            if session is not None:
                return await callback(session)
            return await run_in_transaction(self.client, callback)
        except SessionReuseDetected as exc:
            await self.revoke_all_for_admin(exc.admin_id)
            raise

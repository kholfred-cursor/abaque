"""Public vote persistence (anonymous mode, lot 1) and the ballot reader for exports.

The ONLY write path for ballots. It follows section 7: one transaction, the opening lock
and the quota in a single write on the version, then the ballot and its votes. No
timestamp, no identity, no idempotency key; the response carries no ballot id.
"""

from __future__ import annotations

import random
import uuid
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import AsyncMongoClient
from pymongo.asynchronous.client_session import AsyncClientSession
from pymongo.asynchronous.database import AsyncDatabase

from app.db.client import run_in_transaction
from app.domain.errors import NotFound
from app.domain.vote import (
    BallotQuotaFull,
    BallotRecord,
    ContentChanged,
    PublicView,
    VersionClosed,
    VoteRecord,
)
from app.entitlements.checker import resolve
from app.repositories.mongo.base import TenantScopedRepository
from app.repositories.mongo.content import (
    evaluation_from_document,
    read_content,
    version_from_document,
)

_SYSTEM_RANDOM = random.SystemRandom()


def _oid(value: str) -> ObjectId | None:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        return None


class PublicVoteRepository:
    """Outside any tenant scope: reached through the public slug only."""

    def __init__(self, database: AsyncDatabase[Any], client: AsyncMongoClient[Any]) -> None:
        self.database = database
        self.client = client

    async def find_by_slug(self, slug: str) -> PublicView:
        evaluation = await self.database["evaluations"].find_one({"slug": slug})
        if evaluation is None:
            raise NotFound("Resource not found")
        organization = await self.database["organizations"].find_one(
            {"_id": evaluation["organization_id"], "status": "active"}
        )
        if organization is None:
            raise NotFound("Resource not found")
        version = await self.database["versions"].find_one(
            {
                "organization_id": evaluation["organization_id"],
                "evaluation_id": evaluation["_id"],
                "status": "open",
            }
        )
        content = None
        if version is not None:
            content = await read_content(
                self.database, evaluation["organization_id"], version_from_document(version)
            )
        entitlements = resolve(
            str(organization["plan_code"]), organization.get("entitlements") or {}
        )
        return PublicView(
            organization_id=str(evaluation["organization_id"]),
            evaluation=evaluation_from_document(evaluation),
            content=content,
            max_ballots=entitlements.max_ballots_per_version,
        )

    async def submit_anonymous(
        self,
        organization_id: str,
        evaluation_id: str,
        version_id: str,
        max_ballots: int | None,
        votes: list[VoteRecord],
        day: str,
    ) -> None:
        """Write one anonymous ballot (section 7, steps 1, 3 and 5)."""
        organization_oid = ObjectId(organization_id)
        evaluation_oid = ObjectId(evaluation_id)
        version_oid = _oid(version_id)
        if version_oid is None:
            raise VersionClosed

        async def write(session: AsyncClientSession) -> None:
            # Step 1: opening lock and quota in ONE write. A concurrent close (or content
            # save) writes the same document, so the two transactions conflict.
            lock: dict[str, Any] = {
                "_id": version_oid,
                "organization_id": organization_oid,
                "evaluation_id": evaluation_oid,
                "status": "open",
            }
            if max_ballots is not None:
                lock["ballot_count"] = {"$lt": max_ballots}
            result = await self.database["versions"].update_one(
                lock, {"$inc": {"ballot_count": 1}}, session=session
            )
            if result.modified_count != 1:
                current = await self.database["versions"].find_one(
                    {"_id": version_oid, "organization_id": organization_oid},
                    {"status": 1},
                    session=session,
                )
                if current is None or current["status"] != "open":
                    raise VersionClosed
                raise BallotQuotaFull

            item_ids = set(
                await self.database["items"].distinct(
                    "_id",
                    {"organization_id": organization_oid, "version_id": version_oid},
                    session=session,
                )
            )
            vote_items = [_oid(vote.item_id) for vote in votes]
            if any(item is None or item not in item_ids for item in vote_items):
                raise ContentChanged

            # Step 3: ids and rand_key drawn inside the callback (a retried callback draws
            # new ones; with_transaction never commits the same callback twice).
            ballot_id = str(uuid.uuid4())
            await self.database["ballots"].insert_one(
                {
                    "_id": ballot_id,
                    "organization_id": organization_oid,
                    "version_id": version_oid,
                    "submitted_on": day,
                    "groups": [],
                    "rand_key": _SYSTEM_RANDOM.random(),
                },
                session=session,
            )
            await self.database["votes"].insert_many(
                [
                    {
                        "_id": str(uuid.uuid4()),
                        "organization_id": organization_oid,
                        "ballot_id": ballot_id,
                        "item_id": item,
                        "color_key": vote.color_key,
                        "comment": vote.comment,
                        "comment_status": vote.comment_status,
                    }
                    for vote, item in zip(votes, vote_items, strict=True)
                ],
                session=session,
            )

        await run_in_transaction(self.client, write)

    async def count_ballot_usage(self, organization_id: str, month: str) -> None:
        """Monthly usage counter, best effort and OUTSIDE the vote transaction: writing the
        organization document in every ballot would serialize all votes of a tenant."""
        await self.database["organizations"].update_one(
            {"_id": ObjectId(organization_id)}, {"$inc": {f"usage.{month}.ballots": 1}}
        )


class MongoBallotReader(TenantScopedRepository):
    """Implements BallotReaderPort: ballots of one version, sorted by rand_key only."""

    async def list_by_rand_key(
        self, version_id: str, session: object | None = None
    ) -> list[BallotRecord]:
        version_oid = self._to_object_id(version_id)
        ballots = [
            document["_id"]
            async for document in self.database["ballots"]
            .find(self._scope({"version_id": version_oid}), {"_id": 1})
            .sort("rand_key", 1)
        ]
        votes: dict[str, dict[str, VoteRecord]] = {ballot: {} for ballot in ballots}
        async for document in self.database["votes"].find(
            self._scope({"ballot_id": {"$in": ballots}})
        ):
            votes[document["ballot_id"]][str(document["item_id"])] = VoteRecord(
                item_id=str(document["item_id"]),
                color_key=document["color_key"],
                comment=document.get("comment"),
                comment_status=document["comment_status"],
            )
        return [BallotRecord(votes=votes[ballot]) for ballot in ballots]

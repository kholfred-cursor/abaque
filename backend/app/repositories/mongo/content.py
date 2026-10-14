"""Tenant-scoped persistence of evaluations, versions and their content. Lot 1.

Every multi-collection write runs in one transaction. Content saves and lifecycle
transitions always WRITE the version document, so they conflict inside MongoDB with a
concurrent ballot (which increments ballot_count on the same document).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from pymongo import AsyncMongoClient, ReturnDocument
from pymongo.asynchronous.client_session import AsyncClientSession
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError

from app.db.client import run_in_transaction
from app.domain.content import (
    COLOR_ORDER,
    TRANSITIONS,
    ColorKey,
    Evaluation,
    EvaluationCreate,
    GroupInput,
    Item,
    ItemGroup,
    TransitionAction,
    Version,
    VersionContent,
    as_inputs,
)
from app.domain.errors import (
    AnotherVersionOpen,
    ContentConflict,
    ContentLocked,
    InvalidTransition,
    NotFound,
)
from app.domain.models import TenantContext
from app.repositories.mongo.base import TenantScopedRepository

# Collections holding one document per version (deleted with their version).
_VERSION_SCOPED = (
    "item_groups",
    "items",
    "color_labels",
    "glossary",
    "segment_questions",
    "general_questions",
    "participants",
    "participant_links",
    "credential_uses",
    "email_logs",
    "version_events",
)
# Vote-domain collections keyed by ballot_id.
_BALLOT_SCOPED = ("votes", "segment_answers", "general_answers")

_EVENT_BY_ACTION: dict[TransitionAction, str] = {
    "open": "opened",
    "close": "closed",
    "reopen": "reopened",
    "archive": "archived",
}


class SlugTaken(Exception):  # noqa: N818
    """The randomly generated public slug collided; the caller draws another one."""


def _evaluation(document: dict[str, Any]) -> Evaluation:
    return Evaluation(
        id=str(document["_id"]),
        title=document["title"],
        description=document.get("description"),
        slug=document["slug"],
        participation_mode=document["participation_mode"],
        vote_preset=document["vote_preset"],
        intro_md=document.get("intro_md"),
        outro_md=document.get("outro_md"),
        show_vote_example=document["show_vote_example"],
        anonymity_threshold=document["anonymity_threshold"],
        created_at=document["created_at"],
    )


def _version(document: dict[str, Any]) -> Version:
    return Version(
        id=str(document["_id"]),
        evaluation_id=str(document["evaluation_id"]),
        label=document["label"],
        status=document["status"],
        ballot_count=document["ballot_count"],
        content_revision=document.get("content_revision", 0),
        closed_at=document.get("closed_at"),
    )


class ContentRepository(TenantScopedRepository):
    def __init__(
        self,
        database: AsyncDatabase[Any],
        client: AsyncMongoClient[Any],
        context: TenantContext,
    ) -> None:
        super().__init__(database, context)
        self.client = client

    def _oid(self, value: str) -> ObjectId:
        return self._to_object_id(value)

    # ── Evaluations ──────────────────────────────────────────────────────────

    async def list_evaluations(self) -> list[tuple[Evaluation, list[Version]]]:
        evaluations = [
            _evaluation(document)
            async for document in self.database["evaluations"]
            .find(self._scope())
            .sort("created_at", -1)
        ]
        versions: dict[str, list[Version]] = {}
        async for document in self.database["versions"].find(self._scope()).sort([("_id", 1)]):
            version = _version(document)
            versions.setdefault(version.evaluation_id, []).append(version)
        return [(evaluation, versions.get(evaluation.id, [])) for evaluation in evaluations]

    async def get_evaluation(
        self, evaluation_id: str, session: AsyncClientSession | None = None
    ) -> Evaluation:
        document = await self.database["evaluations"].find_one(
            self._scope({"_id": self._oid(evaluation_id)}), **self._session_options(session)
        )
        if document is None:
            raise NotFound("Resource not found")
        return _evaluation(document)

    async def list_versions(
        self, evaluation_id: str, session: AsyncClientSession | None = None
    ) -> list[Version]:
        cursor = (
            self.database["versions"]
            .find(
                self._scope({"evaluation_id": self._oid(evaluation_id)}),
                **self._session_options(session),
            )
            .sort([("_id", 1)])
        )
        return [_version(document) async for document in cursor]

    async def count_active_evaluations(self, session: AsyncClientSession | None = None) -> int:
        """Evaluations with at least one non-archived version (D042)."""
        ids = await self.database["versions"].distinct(
            "evaluation_id",
            self._scope({"status": {"$ne": "archived"}}),
            **self._session_options(session),
        )
        return len(ids)

    async def create_evaluation(
        self,
        data: EvaluationCreate,
        version_label: str,
        groups: list[GroupInput],
        color_labels: dict[ColorKey, str],
        month: str,
        max_active: int | None,
    ) -> tuple[Evaluation, Version]:
        """Create an evaluation with its first draft version and content, atomically.

        The monthly usage counter is incremented on the organization document inside the
        transaction: two concurrent creations conflict there, so the quota check is exact.
        Raises SlugTaken on a slug collision and QuotaFull when the quota is reached.
        """

        async def create(session: AsyncClientSession) -> tuple[Evaluation, Version]:
            await self.database["organizations"].update_one(
                {"_id": self._organization_id},
                {"$inc": {f"usage.{month}.evaluations": 1}},
                session=session,
            )
            if (
                max_active is not None
                and await self.count_active_evaluations(session) >= max_active
            ):
                raise QuotaFull
            now = datetime.now(UTC)
            evaluation_document: dict[str, Any] = {
                "_id": ObjectId(),
                "organization_id": self._organization_id,
                "admin_id": self._oid(self.context.admin_id),
                "title": data.title,
                "description": data.description,
                "language": "fr",
                "participation_mode": data.participation_mode,
                "slug": data.slug,
                "vote_preset": data.vote_preset,
                "intro_md": data.intro_md,
                "outro_md": data.outro_md,
                "show_vote_example": data.show_vote_example,
                "anonymity_threshold": data.anonymity_threshold,
                "settings": {},
                "created_at": now,
            }
            await self.database["evaluations"].insert_one(evaluation_document, session=session)
            version_document = self._new_version_document(evaluation_document["_id"], version_label)
            await self.database["versions"].insert_one(version_document, session=session)
            await self._insert_content(version_document["_id"], groups, color_labels, {}, session)
            return _evaluation(evaluation_document), _version(version_document)

        try:
            return await run_in_transaction(self.client, create)
        except DuplicateKeyError as exc:
            if "slug" in str((exc.details or {}).get("keyPattern", {})):
                raise SlugTaken from exc
            raise

    async def update_evaluation(self, evaluation_id: str, fields: dict[str, Any]) -> Evaluation:
        document = await self.database["evaluations"].find_one_and_update(
            self._scope({"_id": self._oid(evaluation_id)}),
            {"$set": fields},
            return_document=ReturnDocument.AFTER,
        )
        if document is None:
            raise NotFound("Resource not found")
        return _evaluation(document)

    async def evaluation_has_ballots(self, evaluation_id: str) -> bool:
        found = await self.database["versions"].find_one(
            self._scope({"evaluation_id": self._oid(evaluation_id), "ballot_count": {"$gt": 0}}),
            {"_id": 1},
        )
        return found is not None

    async def delete_evaluation(self, evaluation_id: str) -> None:
        """Delete the evaluation and EVERYTHING attached to it, in one transaction."""
        evaluation_oid = self._oid(evaluation_id)

        async def delete(session: AsyncClientSession) -> None:
            evaluation = await self.database["evaluations"].find_one(
                self._scope({"_id": evaluation_oid}), {"_id": 1}, session=session
            )
            if evaluation is None:
                raise NotFound("Resource not found")
            version_ids = await self.database["versions"].distinct(
                "_id", self._scope({"evaluation_id": evaluation_oid}), session=session
            )
            ballot_ids = await self.database["ballots"].distinct(
                "_id", self._scope({"version_id": {"$in": version_ids}}), session=session
            )
            for name in _BALLOT_SCOPED:
                await self.database[name].delete_many(
                    self._scope({"ballot_id": {"$in": ballot_ids}}), session=session
                )
            await self.database["ballots"].delete_many(
                self._scope({"version_id": {"$in": version_ids}}), session=session
            )
            for name in _VERSION_SCOPED:
                await self.database[name].delete_many(
                    self._scope({"version_id": {"$in": version_ids}}), session=session
                )
            await self.database["versions"].delete_many(
                self._scope({"_id": {"$in": version_ids}}), session=session
            )
            await self.database["evaluations"].delete_one(
                self._scope({"_id": evaluation_oid}), session=session
            )

        await run_in_transaction(self.client, delete)

    # ── Versions ─────────────────────────────────────────────────────────────

    def _new_version_document(self, evaluation_oid: ObjectId, label: str) -> dict[str, Any]:
        return {
            "_id": ObjectId(),
            "organization_id": self._organization_id,
            "evaluation_id": evaluation_oid,
            "label": label,
            "status": "draft",
            "is_visible": True,
            "ballot_count": 0,
            "content_revision": 0,
            "credential_key_id": None,
            "closed_at": None,
            "purge_at": None,
        }

    async def get_version(
        self, version_id: str, session: AsyncClientSession | None = None
    ) -> Version:
        document = await self.database["versions"].find_one(
            self._scope({"_id": self._oid(version_id)}), **self._session_options(session)
        )
        if document is None:
            raise NotFound("Resource not found")
        return _version(document)

    async def get_content(
        self, version_id: str, session: AsyncClientSession | None = None
    ) -> VersionContent:
        version = await self.get_version(version_id, session)
        return await read_content(self.database, self._organization_id, version, session)

    async def _insert_content(
        self,
        version_oid: ObjectId,
        groups: list[GroupInput],
        color_labels: dict[ColorKey, str],
        known_ids: dict[str, dict[str, ObjectId]],
        session: AsyncClientSession,
    ) -> None:
        """Insert groups, items and labels; ids already in the version are kept."""
        group_documents: list[dict[str, Any]] = []
        item_documents: list[dict[str, Any]] = []
        position = 0
        for group_position, group in enumerate(groups):
            group_oid = known_ids.get("item_groups", {}).get(group.id or "") or ObjectId()
            group_documents.append(
                {
                    "_id": group_oid,
                    "organization_id": self._organization_id,
                    "version_id": version_oid,
                    "name": group.name,
                    "position": group_position,
                }
            )
            for item in group.items:
                item_documents.append(
                    {
                        "_id": known_ids.get("items", {}).get(item.id or "") or ObjectId(),
                        "organization_id": self._organization_id,
                        "version_id": version_oid,
                        "group_id": group_oid,
                        "short_name": item.short_name,
                        "statement": item.statement,
                        "position": position,
                    }
                )
                position += 1
        if group_documents:
            await self.database["item_groups"].insert_many(group_documents, session=session)
        if item_documents:
            await self.database["items"].insert_many(item_documents, session=session)
        label_documents = [
            {
                "_id": ObjectId(),
                "organization_id": self._organization_id,
                "version_id": version_oid,
                "color_key": key,
                "label": label,
            }
            for key, label in color_labels.items()
        ]
        if label_documents:
            await self.database["color_labels"].insert_many(label_documents, session=session)

    async def replace_content(
        self,
        version_id: str,
        expected_revision: int,
        groups: list[GroupInput],
        color_labels: dict[ColorKey, str],
    ) -> VersionContent:
        """Replace the whole content of an editable version (no ballot, not archived)."""
        version_oid = self._oid(version_id)

        async def replace(session: AsyncClientSession) -> VersionContent:
            revision_filter: Any = (
                {"$in": [0, None]} if expected_revision == 0 else expected_revision
            )
            result = await self.database["versions"].update_one(
                self._scope(
                    {
                        "_id": version_oid,
                        "ballot_count": 0,
                        "status": {"$ne": "archived"},
                        "content_revision": revision_filter,
                    }
                ),
                {"$inc": {"content_revision": 1}},
                session=session,
            )
            if result.modified_count != 1:
                current = await self.get_version(version_id, session)  # NotFound if foreign
                if current.ballot_count > 0 or current.status == "archived":
                    raise ContentLocked
                raise ContentConflict
            known: dict[str, dict[str, ObjectId]] = {}
            for name in ("item_groups", "items"):
                ids = await self.database[name].distinct(
                    "_id", self._scope({"version_id": version_oid}), session=session
                )
                known[name] = {str(oid): oid for oid in ids}
            for name in ("item_groups", "items", "color_labels"):
                await self.database[name].delete_many(
                    self._scope({"version_id": version_oid}), session=session
                )
            await self._insert_content(version_oid, groups, color_labels, known, session)
            return await self.get_content(version_id, session)

        return await run_in_transaction(self.client, replace)

    async def duplicate_version(self, version_id: str) -> Version:
        """Copy a version's content into a new draft version of the same evaluation."""

        async def duplicate(session: AsyncClientSession) -> Version:
            content = await self.get_content(version_id, session)
            evaluation_oid = self._oid(content.version.evaluation_id)
            count = await self.database["versions"].count_documents(
                self._scope({"evaluation_id": evaluation_oid}), session=session
            )
            document = self._new_version_document(evaluation_oid, f"V{count + 1}")
            await self.database["versions"].insert_one(document, session=session)
            await self._insert_content(
                document["_id"], as_inputs(content), content.color_labels, {}, session
            )
            return _version(document)

        return await run_in_transaction(self.client, duplicate)

    async def transition(self, version_id: str, action: TransitionAction, key_id: str) -> Version:
        """Apply one lifecycle action and journal it, atomically (D037)."""
        version_oid = self._oid(version_id)
        allowed_from, target = TRANSITIONS[action]

        async def apply(session: AsyncClientSession) -> Version:
            now = datetime.now(UTC)
            changes: dict[str, Any] = {"status": target}
            if target == "open":
                changes["credential_key_id"] = key_id
            if action == "close":
                changes["closed_at"] = now
            document = await self.database["versions"].find_one_and_update(
                self._scope({"_id": version_oid, "status": {"$in": list(allowed_from)}}),
                {"$set": changes},
                return_document=ReturnDocument.AFTER,
                session=session,
            )
            if document is None:
                await self.get_version(version_id, session)  # NotFound if absent or foreign
                raise InvalidTransition
            await self.database["version_events"].insert_one(
                {
                    "_id": ObjectId(),
                    "organization_id": self._organization_id,
                    "version_id": version_oid,
                    "kind": _EVENT_BY_ACTION[action],
                    "at": now,
                    "admin_id": self._oid(self.context.admin_id),
                },
                session=session,
            )
            return _version(document)

        try:
            return await run_in_transaction(self.client, apply)
        except DuplicateKeyError as exc:  # uq_versions_evaluation_id_open
            raise AnotherVersionOpen from exc

    async def record_event(self, version_id: str, kind: str) -> None:
        """Journal an action without its content (e.g. an export generation)."""
        await self.database["version_events"].insert_one(
            {
                "_id": ObjectId(),
                "organization_id": self._organization_id,
                "version_id": self._oid(version_id),
                "kind": kind,
                "at": datetime.now(UTC),
                "admin_id": self._oid(self.context.admin_id),
            }
        )

    async def version_events(self, version_id: str) -> list[tuple[str, datetime]]:
        cursor = (
            self.database["version_events"]
            .find(self._scope({"version_id": self._oid(version_id)}))
            .sort("at", 1)
        )
        return [(document["kind"], document["at"]) async for document in cursor]


async def read_content(
    database: AsyncDatabase[Any],
    organization_oid: ObjectId,
    version: Version,
    session: AsyncClientSession | None = None,
) -> VersionContent:
    """Groups, items and labels of a version already resolved within its organization.

    Shared by the tenant-scoped editor and the public vote page (which has no tenant
    context but has read the version through its public slug).
    """
    scope = {"organization_id": organization_oid, "version_id": ObjectId(version.id)}
    options: dict[str, Any] = {} if session is None else {"session": session}
    groups = [
        document
        async for document in database["item_groups"].find(scope, **options).sort("position", 1)
    ]
    items_by_group: dict[Any, list[Item]] = {group["_id"]: [] for group in groups}
    async for document in database["items"].find(scope, **options).sort("position", 1):
        items_by_group.setdefault(document["group_id"], []).append(
            Item(
                id=str(document["_id"]),
                short_name=document["short_name"],
                statement=document["statement"],
            )
        )
    labels: dict[ColorKey, str] = {}
    async for document in database["color_labels"].find(scope, **options):
        labels[document["color_key"]] = document["label"]
    return VersionContent(
        version=version,
        groups=[
            ItemGroup(id=str(group["_id"]), name=group["name"], items=items_by_group[group["_id"]])
            for group in groups
        ],
        color_labels={key: labels[key] for key in COLOR_ORDER if key in labels},
    )


def evaluation_from_document(document: dict[str, Any]) -> Evaluation:
    return _evaluation(document)


def version_from_document(document: dict[str, Any]) -> Version:
    return _version(document)


class QuotaFull(Exception):  # noqa: N818
    """Raised inside the creation transaction when max_active_evaluations is reached."""

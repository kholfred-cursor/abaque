"""MongoDB repositories for tenant-scoped admins and authentication lookup."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.asynchronous.client_session import AsyncClientSession
from pymongo.asynchronous.database import AsyncDatabase

from app.core.identity import normalize_email
from app.domain.errors import NotFound
from app.domain.models import Admin, AdminCreate
from app.entitlements.checker import check_limit
from app.entitlements.models import Entitlements
from app.repositories.mongo.base import TenantScopedRepository
from app.repositories.mongo.organizations import admin_from_document


class AdminRepository(TenantScopedRepository):
    """Administrator repository that is always constrained to one organization."""

    async def get(self, admin_id: str, session: AsyncClientSession | None = None) -> Admin:
        """Find one administrator within the current tenant, otherwise hide its existence."""
        document = await self.database["admins"].find_one(
            self._scope({"_id": self._to_object_id(admin_id)}),
            **self._session_options(session),
        )
        if document is None:
            raise NotFound("Resource not found")
        return admin_from_document(dict(document))

    async def list(self, session: AsyncClientSession | None = None) -> list[Admin]:
        """List the administrators belonging to the current organization only."""
        cursor = self.database["admins"].find(self._scope(), **self._session_options(session))
        documents = await cursor.to_list(None)
        return [admin_from_document(dict(document)) for document in documents]

    async def create_animator(
        self,
        animator: AdminCreate,
        entitlements: Entitlements,
        session: AsyncClientSession | None = None,
    ) -> Admin:
        """Create one animator after enforcing the tenant's animator quota."""
        options = self._session_options(session)
        current = await self.database["admins"].count_documents(
            self._scope({"role": "animator"}), **options
        )
        check_limit(entitlements, "max_animators", current)
        document = self._force_organization(
            {
                "_id": ObjectId(),
                "email": normalize_email(animator.email),
                "email_verified": animator.email_verified,
                "password_hash": animator.password_hash,
                "role": "animator",
                "totp_secret_enc": None,
                "created_at": datetime.now(UTC),
                "organization_id": animator.organization_id,
            }
        )
        await self.database["admins"].insert_one(document, **options)
        return admin_from_document(document)


class AdminAuthRepository:
    """Authentication-only repository deliberately outside a tenant query scope."""

    def __init__(self, database: AsyncDatabase[Any]) -> None:
        self.database = database

    @staticmethod
    def _session_options(session: AsyncClientSession | None) -> dict[str, Any]:
        return {} if session is None else {"session": session}

    @staticmethod
    def _to_object_id(identifier: str) -> ObjectId:
        try:
            return ObjectId(identifier)
        except Exception as exc:
            raise NotFound("Resource not found") from exc

    async def find_by_email(
        self, email: str, session: AsyncClientSession | None = None
    ) -> Admin | None:
        """Find a login account by the application's sole normalized email representation."""
        document = await self.database["admins"].find_one(
            {"email": normalize_email(email)}, **self._session_options(session)
        )
        return None if document is None else admin_from_document(dict(document))

    async def create_owner(
        self, organization_id: str, owner: AdminCreate, session: AsyncClientSession | None = None
    ) -> Admin:
        """Create an owner for an organization inside a caller-owned transaction when needed."""
        document: dict[str, Any] = {
            "_id": ObjectId(),
            "organization_id": self._to_object_id(organization_id),
            "email": normalize_email(owner.email),
            "email_verified": owner.email_verified,
            "password_hash": owner.password_hash,
            "role": "owner",
            "totp_secret_enc": None,
            "created_at": datetime.now(UTC),
        }
        await self.database["admins"].insert_one(document, **self._session_options(session))
        return admin_from_document(document)

    async def mark_email_verified(
        self, admin_id: str, session: AsyncClientSession | None = None
    ) -> Admin:
        """Mark an account verified and return its updated domain model."""
        document = await self.database["admins"].find_one_and_update(
            {"_id": self._to_object_id(admin_id)},
            {"$set": {"email_verified": True}},
            return_document=ReturnDocument.AFTER,
            **self._session_options(session),
        )
        if document is None:
            raise NotFound("Resource not found")
        return admin_from_document(dict(document))

    async def set_password_hash(
        self, admin_id: str, password_hash: str, session: AsyncClientSession | None = None
    ) -> Admin:
        """Replace a password hash without accepting any raw password in this layer."""
        document = await self.database["admins"].find_one_and_update(
            {"_id": self._to_object_id(admin_id)},
            {"$set": {"password_hash": password_hash}},
            return_document=ReturnDocument.AFTER,
            **self._session_options(session),
        )
        if document is None:
            raise NotFound("Resource not found")
        return admin_from_document(dict(document))

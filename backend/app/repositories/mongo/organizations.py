"""MongoDB repository for organization creation, current tenant, and usage."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from bson import ObjectId
from pymongo import AsyncMongoClient
from pymongo.asynchronous.client_session import AsyncClientSession
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError

from app.core.identity import normalize_email
from app.db.client import run_in_transaction
from app.domain.errors import EmailAlreadyRegistered, NotFound
from app.domain.models import (
    Admin,
    AdminCreate,
    Organization,
    OrganizationCreate,
    UsageKey,
)
from app.entitlements.checker import resolve
from app.entitlements.models import Entitlements
from app.repositories.mongo.base import TenantScopedRepository


def organization_from_document(document: dict[str, Any]) -> Organization:
    """Convert a MongoDB organization document into its domain model."""
    usage = cast(dict[str, dict[UsageKey, int]], document["usage"])
    return Organization(
        id=str(document["_id"]),
        name=str(document["name"]),
        slug=str(document["slug"]),
        plan_code=document["plan_code"],
        status=document["status"],
        # Stored entitlements are partial overrides of the plan defaults (D028):
        # changing plan_code or PLAN_DEFAULTS takes effect without rewriting documents.
        entitlements=resolve(str(document["plan_code"]), document.get("entitlements") or {}),
        usage=usage,
        trial_ends_at=document.get("trial_ends_at"),
        created_at=document["created_at"],
    )


def admin_from_document(document: dict[str, Any]) -> Admin:
    """Convert a MongoDB administrator document into its domain model."""
    organization_id = document.get("organization_id")
    return Admin(
        id=str(document["_id"]),
        organization_id=None if organization_id is None else str(organization_id),
        email=str(document["email"]),
        email_verified=bool(document["email_verified"]),
        password_hash=str(document["password_hash"]),
        role=document["role"],
        totp_secret_enc=document.get("totp_secret_enc"),
        created_at=document["created_at"],
    )


class OrganizationProvisioningRepository:
    """Signup-only repository, deliberately outside any tenant scope (no tenant exists yet)."""

    def __init__(self, database: AsyncDatabase[Any], client: AsyncMongoClient[Any]) -> None:
        self.database = database
        self.client = client

    async def create_with_owner(
        self, organization: OrganizationCreate, owner: AdminCreate
    ) -> tuple[Organization, Admin]:
        """Atomically create an organization and its first owner."""
        overrides = dict(organization.entitlement_overrides or {})
        resolve(organization.plan_code, overrides)  # reject invalid overrides before writing

        async def create(session: AsyncClientSession) -> tuple[Organization, Admin]:
            now = datetime.now(UTC)
            organization_id = ObjectId()
            organization_document: dict[str, Any] = {
                "_id": organization_id,
                "name": organization.name,
                "slug": organization.slug,
                "plan_code": organization.plan_code,
                "status": "active",
                "entitlements": overrides,
                "usage": {},
                "trial_ends_at": organization.trial_ends_at,
                "created_at": now,
            }
            owner_document: dict[str, Any] = {
                "_id": ObjectId(),
                "organization_id": organization_id,
                "email": normalize_email(owner.email),
                "email_verified": owner.email_verified,
                "password_hash": owner.password_hash,
                "role": "owner",
                "totp_secret_enc": None,
                "created_at": now,
            }
            await self.database["organizations"].insert_one(organization_document, session=session)
            await self.database["admins"].insert_one(owner_document, session=session)
            return (
                organization_from_document(organization_document),
                admin_from_document(owner_document),
            )

        try:
            return await run_in_transaction(self.client, create)
        except DuplicateKeyError as exc:
            if "email" in str((exc.details or {}).get("keyPattern", {})):
                raise EmailAlreadyRegistered from exc
            raise


class OrganizationRepository(TenantScopedRepository):
    """The authenticated tenant's own organization: read, entitlements, usage counters."""

    async def get_current(self, session: AsyncClientSession | None = None) -> Organization:
        """Get the organization referenced by the authenticated tenant context."""
        document = await self.database["organizations"].find_one(
            {"_id": self._organization_id}, **self._session_options(session)
        )
        if document is None:
            raise NotFound("Resource not found")
        return organization_from_document(dict(document))

    async def get_entitlements(self, session: AsyncClientSession | None = None) -> Entitlements:
        """Return the resolved entitlements stored for the current organization."""
        return (await self.get_current(session)).entitlements

    async def increment_usage(
        self,
        month: str,
        key: UsageKey,
        increment: int,
        session: AsyncClientSession | None = None,
    ) -> None:
        """Atomically increment one monthly organization usage counter."""
        result = await self.database["organizations"].update_one(
            {"_id": self._organization_id},
            {"$inc": {f"usage.{month}.{key}": increment}},
            **self._session_options(session),
        )
        if result.matched_count != 1:
            raise NotFound("Resource not found")

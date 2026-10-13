"""Development-only idempotent demo seed data."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from pymongo.asynchronous.database import AsyncDatabase

from app.core.config import Settings
from app.core.security import hash_password

logger = logging.getLogger(__name__)


def _entitlements() -> dict[str, Any]:
    return {
        "max_active_evaluations": None,
        "max_ballots_per_version": None,
        "max_animators": None,
        "modes_allowed": ["anonymous", "auth_open", "auth_closed"],
        "pdf_export": True,
        "csv_export": True,
        "email_invitations": True,
        "custom_branding": False,
        "retention_months": None,
    }


async def _seed_organization(
    database: AsyncDatabase[Any],
    *,
    name: str,
    slug: str,
    plan_code: str,
) -> ObjectId:
    organization = {
        "_id": ObjectId(),
        "name": name,
        "slug": slug,
        "plan_code": plan_code,
        "status": "active",
        "entitlements": _entitlements(),
        "usage": {},
        "trial_ends_at": None,
        "created_at": datetime.now(UTC),
    }
    await database["organizations"].update_one(
        {"slug": slug},
        {"$setOnInsert": organization},
        upsert=True,
    )
    stored = await database["organizations"].find_one({"slug": slug}, {"_id": 1})
    if stored is None:
        raise RuntimeError("Demo organization could not be loaded after its upsert")
    organization_id = stored["_id"]
    if not isinstance(organization_id, ObjectId):
        raise RuntimeError("Demo organization has an invalid identifier")
    return organization_id


async def _seed_admin(
    database: AsyncDatabase[Any],
    *,
    email: str,
    organization_id: ObjectId,
) -> None:
    admin = {
        "_id": ObjectId(),
        "organization_id": organization_id,
        "email": email,
        "email_verified": True,
        # This is the sole intentional bypass of the production password policy.
        "password_hash": hash_password("admin"),
        "role": "owner",
        "totp_secret_enc": None,
        "created_at": datetime.now(UTC),
    }
    await database["admins"].update_one(
        {"email": email},
        {"$setOnInsert": admin},
        upsert=True,
    )


async def seed_demo(database: AsyncDatabase[Any], settings: Settings) -> bool:
    """Create isolated demo tenants only in an explicitly seeded development environment."""
    if not settings.SEED_DEMO or settings.ENVIRONMENT != "development":
        return False

    demo_organization_id = await _seed_organization(
        database,
        name="Démo",
        slug="demo",
        plan_code="trial",
    )
    other_organization_id = await _seed_organization(
        database,
        name="Autre",
        slug="autre",
        plan_code="trial",
    )
    await _seed_admin(
        database,
        email="admin@demo.example.com",
        organization_id=demo_organization_id,
    )
    await _seed_admin(
        database,
        email="other@demo.example.com",
        organization_id=other_organization_id,
    )
    logger.info("Development demo seed applied")
    return True

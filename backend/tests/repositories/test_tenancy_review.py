"""Additional block 4a checks: atomicity under failCommand, quotas, overrides, isolation."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError
from pymongo import AsyncMongoClient
from pymongo.errors import OperationFailure

from app.core.security import hash_password
from app.domain.models import AdminCreate, OrganizationCreate, TenantContext
from app.entitlements.checker import LimitReached, resolve
from app.repositories.mongo.admins import AdminRepository
from app.repositories.mongo.organizations import (
    OrganizationProvisioningRepository,
    OrganizationRepository,
)
from tests.conftest import MigratedDatabase

_HASH = hash_password("a-password-used-only-in-tests")


def _admin(email: str) -> AdminCreate:
    return AdminCreate(email=email, password_hash=_HASH)


async def _tenant(
    db: MigratedDatabase, client: AsyncMongoClient[Any], slug: str, **org: Any
) -> TenantContext:
    organization, owner = await OrganizationProvisioningRepository(
        db.database, client
    ).create_with_owner(
        OrganizationCreate(name=slug.title(), slug=slug, **org), _admin(f"owner@{slug}.example")
    )
    return TenantContext(organization_id=organization.id, admin_id=owner.id, role="owner")


def test_unknown_plan_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown plan"):
        resolve("platinum")


def test_unknown_override_key_is_rejected() -> None:
    with pytest.raises(ValidationError):
        resolve("trial", {"max_everything": 5})


@pytest.mark.integration
async def test_create_with_owner_rolls_back_when_the_server_fails_the_owner_insert(
    migrated_database: MigratedDatabase, mongo_client: AsyncMongoClient[Any]
) -> None:
    """failCommand on the admins insert: the organization insert must be rolled back."""
    # Fail only the second insert of the transaction (the owner), not the organization.
    await mongo_client.admin.command(
        {
            "configureFailPoint": "failCommand",
            "mode": {"skip": 1},
            "data": {"failCommands": ["insert"], "errorCode": 2},
        }
    )
    try:
        with pytest.raises(OperationFailure):
            await OrganizationProvisioningRepository(
                migrated_database.database, mongo_client
            ).create_with_owner(
                OrganizationCreate(name="Boom", slug="boom"), _admin("owner@boom.example")
            )
    finally:
        await mongo_client.admin.command({"configureFailPoint": "failCommand", "mode": "off"})

    assert await migrated_database.database["organizations"].count_documents({}) == 0
    assert await migrated_database.database["admins"].count_documents({}) == 0


@pytest.mark.integration
async def test_invalid_overrides_write_nothing(
    migrated_database: MigratedDatabase, mongo_client: AsyncMongoClient[Any]
) -> None:
    with pytest.raises(ValidationError):
        await _tenant(
            migrated_database, mongo_client, "bad", entitlement_overrides={"max_animators": -1}
        )
    assert await migrated_database.database["organizations"].count_documents({}) == 0


@pytest.mark.integration
async def test_stored_entitlements_are_overrides_so_a_plan_change_applies(
    migrated_database: MigratedDatabase, mongo_client: AsyncMongoClient[Any]
) -> None:
    """Only overrides are stored: switching plan_code changes the resolved entitlements."""
    context = await _tenant(
        migrated_database, mongo_client, "growing", entitlement_overrides={"max_animators": 3}
    )
    organizations = OrganizationRepository(migrated_database.database, context)
    trial = await organizations.get_entitlements()
    assert (trial.max_animators, trial.max_active_evaluations) == (3, 1)

    stored = await migrated_database.database["organizations"].find_one({"slug": "growing"})
    assert stored is not None
    assert stored["entitlements"] == {"max_animators": 3}

    await migrated_database.database["organizations"].update_one(
        {"slug": "growing"}, {"$set": {"plan_code": "standard"}}
    )
    standard = await organizations.get_entitlements()
    assert (standard.max_animators, standard.max_active_evaluations) == (3, 100)
    assert standard.email_invitations is True


@pytest.mark.integration
async def test_animator_quota_is_enforced(
    migrated_database: MigratedDatabase, mongo_client: AsyncMongoClient[Any]
) -> None:
    context = await _tenant(migrated_database, mongo_client, "small")
    admins = AdminRepository(migrated_database.database, context)
    trial = resolve("trial")

    await admins.create_animator(_admin("first@small.example"), trial)
    with pytest.raises(LimitReached):
        await admins.create_animator(_admin("second@small.example"), trial)
    assert len(await admins.list()) == 2  # owner + one animator


@pytest.mark.integration
async def test_each_tenant_sees_only_its_own_admins_and_usage(
    migrated_database: MigratedDatabase, mongo_client: AsyncMongoClient[Any]
) -> None:
    context_a = await _tenant(migrated_database, mongo_client, "alpha")
    context_b = await _tenant(migrated_database, mongo_client, "beta")
    admins_a = AdminRepository(migrated_database.database, context_a)
    admins_b = AdminRepository(migrated_database.database, context_b)

    assert {a.organization_id for a in await admins_a.list()} == {context_a.organization_id}
    assert {a.organization_id for a in await admins_b.list()} == {context_b.organization_id}

    await OrganizationRepository(migrated_database.database, context_a).increment_usage(
        "2026-10", "ballots", 5
    )
    org_b = await OrganizationRepository(migrated_database.database, context_b).get_current()
    assert org_b.usage == {}

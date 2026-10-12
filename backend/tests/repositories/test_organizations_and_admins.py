"""Integration tests for organization and administrator repositories."""

from __future__ import annotations

from typing import Any

import pytest
from pymongo import AsyncMongoClient
from pymongo.errors import WriteError

from app.core.security import hash_password
from app.domain.errors import NotFound, TenantScopeError
from app.domain.models import AdminCreate, OrganizationCreate, TenantContext
from app.entitlements.checker import resolve
from app.repositories.mongo.admins import AdminAuthRepository, AdminRepository
from app.repositories.mongo.organizations import (
    OrganizationProvisioningRepository,
    OrganizationRepository,
)
from tests.conftest import MigratedDatabase


def _owner(email: str, organization_id: str | None = None) -> AdminCreate:
    return AdminCreate(
        email=email,
        password_hash=hash_password("an-owner-password-for-tests"),
        organization_id=organization_id,
    )


def _organization(name: str, slug: str) -> OrganizationCreate:
    return OrganizationCreate(name=name, slug=slug)


def _context(organization_id: str, admin_id: str) -> TenantContext:
    return TenantContext(organization_id=organization_id, admin_id=admin_id, role="owner")


@pytest.mark.integration
async def test_create_with_owner_writes_both_documents_in_one_transaction(
    migrated_database: MigratedDatabase,
    mongo_client: AsyncMongoClient[dict[str, Any]],
) -> None:
    """A rejected owner insert rolls back the organization insert in the same transaction."""
    repository = OrganizationProvisioningRepository(migrated_database.database, mongo_client)
    invalid_owner = AdminCreate(email="owner@example.com", password_hash="not-an-argon2-hash")

    with pytest.raises(WriteError):
        await repository.create_with_owner(_organization("Atomic", "atomic"), invalid_owner)

    organization_count = await migrated_database.database["organizations"].count_documents(
        {"slug": "atomic"}
    )
    assert organization_count == 0


@pytest.mark.integration
async def test_tenant_repositories_hide_other_organizations_and_force_the_context_tenant(
    migrated_database: MigratedDatabase,
    mongo_client: AsyncMongoClient[dict[str, Any]],
) -> None:
    """Tenant A cannot read B and a caller-supplied tenant id is overwritten on writes."""
    factory = OrganizationProvisioningRepository(migrated_database.database, mongo_client)
    organization_a, owner_a = await factory.create_with_owner(
        _organization("Organisation A", "organization-a"), _owner("owner-a@example.com")
    )
    organization_b, owner_b = await factory.create_with_owner(
        _organization("Organisation B", "organization-b"), _owner("owner-b@example.com")
    )
    repository_a = AdminRepository(
        migrated_database.database, _context(organization_a.id, owner_a.id)
    )

    animator = await repository_a.create_animator(
        _owner("animator-a@example.com", organization_b.id), resolve("standard")
    )

    assert animator.organization_id == organization_a.id
    assert {admin.id for admin in await repository_a.list()} == {owner_a.id, animator.id}
    with pytest.raises(NotFound):
        await repository_a.get(owner_b.id)
    with pytest.raises(TenantScopeError):
        repository_a._scope({"organization_id": organization_b.id})


@pytest.mark.integration
async def test_organization_usage_and_admin_auth_operations_use_domain_models(
    migrated_database: MigratedDatabase,
    mongo_client: AsyncMongoClient[dict[str, Any]],
) -> None:
    """Current organization, usage counters, and global authentication operations stay typed."""
    factory = OrganizationProvisioningRepository(migrated_database.database, mongo_client)
    organization, owner = await factory.create_with_owner(
        _organization("Usage", "usage"), _owner("owner@example.com")
    )
    context = _context(organization.id, owner.id)
    organizations = OrganizationRepository(migrated_database.database, context)
    auth = AdminAuthRepository(migrated_database.database)

    await organizations.increment_usage("2026-10", "evaluations", 1)
    current = await organizations.get_current()
    verified = await auth.mark_email_verified(owner.id)
    updated = await auth.set_password_hash(owner.id, hash_password("a-new-valid-password"))

    assert current.usage["2026-10"]["evaluations"] == 1
    assert (await organizations.get_entitlements()).max_active_evaluations == 1
    assert (await auth.find_by_email("OWNER@example.com")) == updated
    assert verified.email_verified is True

"""Integration tests for the development-only demo seed."""

from __future__ import annotations

import pytest

from app.core.security import verify_password
from app.db.seed import seed_demo
from tests.conftest import MigratedDatabase


@pytest.mark.integration
async def test_demo_seed_is_idempotent(migrated_database: MigratedDatabase) -> None:
    """Repeated seed calls keep exactly two isolated demo tenants and accounts."""
    settings = migrated_database.settings.model_copy(update={"SEED_DEMO": True})

    assert await seed_demo(migrated_database.database, settings) is True
    assert await seed_demo(migrated_database.database, settings) is True

    organizations = await migrated_database.database["organizations"].find({}).to_list(None)
    admins = await migrated_database.database["admins"].find({}).to_list(None)
    admin_by_email = {str(admin["email"]): admin for admin in admins}

    assert {str(organization["name"]) for organization in organizations} == {"Démo", "Autre"}
    assert set(admin_by_email) == {"admin@abaque.local", "other@abaque.local"}
    assert len({admin["organization_id"] for admin in admins}) == 2
    assert verify_password("admin", str(admin_by_email["admin@abaque.local"]["password_hash"]))

"""Concurrency tests for refresh sessions and single-use authentication tokens."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from bson import ObjectId

from app.domain.errors import NotFound
from app.domain.sessions import ConcurrentRotation, SessionReuseDetected
from app.repositories.mongo.auth_tokens import AuthTokenRepository
from app.repositories.mongo.sessions import AdminSessionRepository
from tests.conftest import MigratedDatabase


def _hash(character: str) -> str:
    return character * 64


@pytest.mark.integration
async def test_concurrent_session_rotation_allows_one_success(
    migrated_database: MigratedDatabase, mongo_client: Any
) -> None:
    repository = AdminSessionRepository(migrated_database.database, mongo_client)
    admin_id = str(ObjectId())
    await repository.create(admin_id, _hash("a"), datetime.now(UTC) + timedelta(hours=1))

    results = await asyncio.gather(
        repository.rotate(_hash("a"), _hash("b"), datetime.now(UTC) + timedelta(hours=1)),
        repository.rotate(_hash("a"), _hash("c"), datetime.now(UTC) + timedelta(hours=1)),
        return_exceptions=True,
    )

    assert sum(not isinstance(result, Exception) for result in results) == 1
    assert sum(isinstance(result, ConcurrentRotation) for result in results) == 1
    # A benign two-tab race must not log the administrator out (D029).
    winner = next(result for result in results if not isinstance(result, BaseException))
    stored = await migrated_database.database["admin_sessions"].find_one(
        {"token_hash": winner.token_hash}
    )
    assert stored is not None
    assert stored["revoked_at"] is None


@pytest.mark.integration
async def test_replaying_a_consumed_session_revokes_all_admin_sessions(
    migrated_database: MigratedDatabase, mongo_client: Any
) -> None:
    repository = AdminSessionRepository(migrated_database.database, mongo_client)
    admin_id = str(ObjectId())
    await repository.create(admin_id, _hash("a"), datetime.now(UTC) + timedelta(hours=1))
    await repository.create(admin_id, _hash("f"), datetime.now(UTC) + timedelta(hours=1))
    await repository.rotate(_hash("a"), _hash("b"), datetime.now(UTC) + timedelta(hours=1))
    # Move the rotation outside the grace window: a later replay is a theft signal.
    await migrated_database.database["admin_sessions"].update_one(
        {"token_hash": _hash("a")},
        {"$set": {"consumed_at": datetime.now(UTC) - timedelta(minutes=1)}},
    )

    with pytest.raises(SessionReuseDetected):
        await repository.rotate(_hash("a"), _hash("c"), datetime.now(UTC) + timedelta(hours=1))

    sessions = (
        await migrated_database.database["admin_sessions"]
        .find({"admin_id": ObjectId(admin_id)})
        .to_list(None)
    )
    assert all(session["revoked_at"] is not None for session in sessions)


@pytest.mark.integration
@pytest.mark.parametrize(
    "revoked, expires_at", [(True, timedelta(hours=1)), (False, timedelta(hours=-1))]
)
async def test_revoked_or_expired_session_cannot_rotate(
    migrated_database: MigratedDatabase, mongo_client: Any, revoked: bool, expires_at: timedelta
) -> None:
    repository = AdminSessionRepository(migrated_database.database, mongo_client)
    await repository.create(str(ObjectId()), _hash("a"), datetime.now(UTC) + expires_at)
    if revoked:
        await repository.revoke(_hash("a"))

    with pytest.raises(NotFound):
        await repository.rotate(_hash("a"), _hash("b"), datetime.now(UTC) + timedelta(hours=1))


@pytest.mark.integration
async def test_auth_tokens_are_single_use_and_replace_active_token(
    migrated_database: MigratedDatabase,
) -> None:
    repository = AuthTokenRepository(migrated_database.database)
    admin_id = str(ObjectId())
    expires_at = datetime.now(UTC) + timedelta(hours=1)
    await repository.create(admin_id, "reset_password", _hash("a"), expires_at)
    results = await asyncio.gather(
        *[repository.consume(_hash("a"), "reset_password") for _ in range(10)]
    )
    assert results.count(admin_id) == 1
    assert results.count(None) == 9

    await repository.create(admin_id, "reset_password", _hash("b"), expires_at)
    assert await repository.consume(_hash("a"), "reset_password") is None
    assert await repository.consume(_hash("b"), "verify_email") is None
    await repository.create(
        admin_id, "verify_email", _hash("c"), datetime.now(UTC) - timedelta(seconds=1)
    )
    assert await repository.consume(_hash("c"), "verify_email") is None


@pytest.mark.integration
async def test_replay_within_grace_window_does_not_revoke(
    migrated_database: MigratedDatabase, mongo_client: Any
) -> None:
    repository = AdminSessionRepository(migrated_database.database, mongo_client)
    admin_id = str(ObjectId())
    expires = datetime.now(UTC) + timedelta(hours=1)
    await repository.create(admin_id, _hash("a"), expires)
    await repository.rotate(_hash("a"), _hash("b"), expires)

    with pytest.raises(ConcurrentRotation):
        await repository.rotate(_hash("a"), _hash("c"), expires)

    current = await repository.find_by_hash(_hash("b"))
    assert current is not None
    assert current.revoked_at is None

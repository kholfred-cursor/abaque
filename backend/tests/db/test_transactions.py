"""Block 6: run_in_transaction under server-injected failures (configureFailPoint).

Requires mongod with --setParameter enableTestCommands=1 (CI and docker-compose.test.yml).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

import pytest
import pytest_asyncio
from bson import ObjectId
from pymongo import AsyncMongoClient
from pymongo.asynchronous.client_session import AsyncClientSession

from app.db.client import run_in_transaction
from tests.conftest import MigratedDatabase

pytestmark = pytest.mark.integration

FailPoint = Callable[[dict[str, Any]], Awaitable[None]]


@pytest_asyncio.fixture
async def fail_point(mongo_client: AsyncMongoClient[Any]) -> AsyncIterator[FailPoint]:
    async def enable(data: dict[str, Any]) -> None:
        await mongo_client.admin.command(
            {"configureFailPoint": "failCommand", "mode": {"times": 1}, "data": data}
        )

    try:
        yield enable
    finally:
        await mongo_client.admin.command({"configureFailPoint": "failCommand", "mode": "off"})


def _writer(db: MigratedDatabase, calls: list[int]) -> Callable[[AsyncClientSession], Any]:
    async def callback(session: AsyncClientSession) -> None:
        calls.append(1)
        await db.database["glossary_tx_probe"].insert_one({"_id": ObjectId()}, session=session)

    return callback


async def test_transient_error_on_insert_retries_the_whole_callback(
    migrated_database: MigratedDatabase, mongo_client: AsyncMongoClient[Any], fail_point: FailPoint
) -> None:
    await migrated_database.database.create_collection("glossary_tx_probe")
    await fail_point(
        {"failCommands": ["insert"], "errorCode": 112, "errorLabels": ["TransientTransactionError"]}
    )
    calls: list[int] = []

    await run_in_transaction(mongo_client, _writer(migrated_database, calls))

    assert len(calls) == 2
    assert await migrated_database.database["glossary_tx_probe"].count_documents({}) == 1


async def test_unknown_commit_result_retries_only_the_commit(
    migrated_database: MigratedDatabase, mongo_client: AsyncMongoClient[Any], fail_point: FailPoint
) -> None:
    """D024: a hand-written retry loop would re-run the callback and duplicate a ballot."""
    await migrated_database.database.create_collection("glossary_tx_probe")
    await fail_point(
        {
            "failCommands": ["commitTransaction"],
            "errorCode": 91,
            "errorLabels": ["UnknownTransactionCommitResult"],
        }
    )
    calls: list[int] = []

    await run_in_transaction(mongo_client, _writer(migrated_database, calls))

    assert len(calls) == 1
    assert await migrated_database.database["glossary_tx_probe"].count_documents({}) == 1


async def test_business_error_writes_nothing(
    migrated_database: MigratedDatabase, mongo_client: AsyncMongoClient[Any]
) -> None:
    await migrated_database.database.create_collection("glossary_tx_probe")

    async def callback(session: AsyncClientSession) -> None:
        await migrated_database.database["glossary_tx_probe"].insert_one(
            {"_id": ObjectId()}, session=session
        )
        raise ValueError("limite atteinte")

    with pytest.raises(ValueError, match="limite atteinte"):
        await run_in_transaction(mongo_client, callback)
    assert await migrated_database.database["glossary_tx_probe"].count_documents({}) == 0

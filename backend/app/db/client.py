"""MongoDB async client lifecycle and transaction helper.

The client is created in FastAPI's lifespan and stored in app.state.
Only repositories/ and db/ may import this module (architecture test).
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from typing import Any

from pymongo import AsyncMongoClient, ReadPreference
from pymongo.asynchronous.client_session import AsyncClientSession
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern

logger = logging.getLogger(__name__)


def create_client(mongodb_uri: str) -> AsyncMongoClient[Any]:
    """Create and return an AsyncMongoClient.

    Must be called once in the lifespan, and closed on shutdown.
    """
    return AsyncMongoClient(
        mongodb_uri,
        uuidRepresentation="standard",
        tz_aware=True,
        w="majority",
        readConcernLevel="majority",
        retryWrites=True,
    )


def get_database(client: AsyncMongoClient[Any], database_name: str) -> AsyncDatabase[Any]:
    """Get the application database from the client."""
    return client[database_name]


async def verify_replica_set(client: AsyncMongoClient[Any]) -> None:
    """Verify that the connected MongoDB is a replica set. Raises RuntimeError if not."""
    hello = await client.admin.command("hello")
    if "setName" not in hello:
        msg = (
            "MongoDB is not running as a replica set. "
            "Start mongod with --replSet. See docs/adr/0001-stack.md."
        )
        raise RuntimeError(msg)
    logger.info("Connected to replica set '%s'", hello["setName"])


async def run_in_transaction[T](
    client: AsyncMongoClient[Any],
    callback: Callable[[AsyncClientSession], Coroutine[Any, Any, T]],
) -> T:
    """Execute callback within a transaction using session.with_transaction (D024).

    start_session() returns an async context manager directly (no await).

    The callback:
    - receives the session and must pass it to every DB operation
    - must NOT have side effects outside the database (email, logging, counters)
    - must NOT swallow PyMongoError; business errors are re-raised
    - generates UUIDs and rand_keys inside (safe on retry)

    session.with_transaction handles:
    - TransientTransactionError: retries the entire callback
    - UnknownTransactionCommitResult: retries only the commit
    """
    async with client.start_session() as session:
        result = await session.with_transaction(
            callback,
            read_concern=ReadConcern("majority"),
            write_concern=WriteConcern("majority"),
            read_preference=ReadPreference.PRIMARY,
        )
        return result

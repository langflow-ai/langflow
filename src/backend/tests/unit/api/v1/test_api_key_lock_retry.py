"""API-key writes must survive a stale SQLite WAL snapshot.

Under WAL a connection that has already read cannot be promoted to a writer:
SQLite answers ``SQLITE_BUSY_SNAPSHOT`` immediately and deliberately skips the
busy handler, so ``busy_timeout`` cannot rescue the write. Only ending the
transaction and retrying against a fresh snapshot can, which is what
:func:`run_with_lock_retry` does. These tests pin the routes to that contract
without going through a live client: the ``client`` fixture needs a full
application lifespan, and the property under test is purely about how the route
reacts to a lock error.
"""

from __future__ import annotations

import sqlite3
from unittest.mock import AsyncMock

import pytest
from langflow.services.database.lock_retry import is_database_lock_error, run_with_lock_retry
from sqlalchemy.exc import OperationalError


def _lock_error() -> OperationalError:
    message = "database is locked"
    return OperationalError("INSERT INTO apikey", {}, sqlite3.OperationalError(message))


def _other_error() -> OperationalError:
    message = "no such column: apikey.bogus"
    return OperationalError("INSERT INTO apikey", {}, sqlite3.OperationalError(message))


def test_lock_error_is_recognised() -> None:
    assert is_database_lock_error(_lock_error()) is True


def test_other_error_is_not_retried() -> None:
    assert is_database_lock_error(_other_error()) is False


@pytest.mark.anyio
async def test_retry_reaches_a_fresh_snapshot() -> None:
    calls: list[int] = []

    async def _attempt(attempt: int) -> str:
        calls.append(attempt)
        if attempt < 2:
            raise _lock_error()
        return "ok"

    session = AsyncMock()

    assert await run_with_lock_retry(_attempt, session=session, description="create_api_key") == "ok"
    assert calls == [0, 1, 2]
    # Every retry must drop the stale snapshot before running the operation again.
    assert session.rollback.await_count == 2


@pytest.mark.anyio
async def test_retry_does_not_swallow_other_errors() -> None:
    calls: list[int] = []

    async def _attempt(attempt: int) -> str:
        calls.append(attempt)
        raise _other_error()

    session = AsyncMock()

    with pytest.raises(OperationalError):
        await run_with_lock_retry(_attempt, session=session, description="create_api_key")
    assert calls == [0]
    assert session.rollback.await_count == 0

"""Tests for the schema-migration advisory lock.

Workers booting concurrently against a fresh Postgres race on
``CREATE TYPE`` / ``CREATE TABLE`` because each calls ``alembic upgrade``
independently. ``_postgres_migration_lock`` holds a session-level
``pg_advisory_lock`` for the duration of the upgrade so only one worker
mutates the schema at a time. The lock is acquired via ``pg_try_advisory_lock``
in a bounded polling loop so a hung holder can't block every other worker
forever; the wait emits a log line and times out with an actionable error.

Mocking ``sa.create_engine`` here so the test runs without a real Postgres
instance. The unit under test is the orchestration: which SQL gets executed,
in what order, on which kinds of URLs.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from langflow.services.database.service import (
    _MIGRATION_ADVISORY_LOCK_ID,
    _postgres_migration_lock,
)

_PG_URL = "postgresql+psycopg://host/db"
_SQLITE_URL = "sqlite+aiosqlite:///./langflow.db"
_SERVICE = "langflow.services.database.service"
_CREATE_ENGINE_PATH = f"{_SERVICE}.sa.create_engine"

_BOOM_MESSAGE = "migration exploded"


class _BoomError(RuntimeError):
    """Sentinel exception used to verify the lock releases on failure."""


def _engine_with_conn(*, scalar_returns: list[bool] | bool) -> tuple[MagicMock, MagicMock]:
    """Build a (engine, conn) mock pair where each execute().scalar() returns the next bool."""
    conn_mock = MagicMock()
    if isinstance(scalar_returns, bool):
        conn_mock.execute.return_value.scalar.return_value = scalar_returns
    else:
        conn_mock.execute.return_value.scalar.side_effect = scalar_returns
    engine_mock = MagicMock()
    engine_mock.connect.return_value.__enter__.return_value = conn_mock
    return engine_mock, conn_mock


def _executed_sql(conn_mock: MagicMock) -> list[str]:
    """Return the raw SQL text of each ``execute`` call on a mocked connection."""
    return [str(call.args[0]) for call in conn_mock.execute.call_args_list]


def test_sqlite_url_is_a_noop_no_engine_created():
    """SQLite has no advisory locks; entering the lock must not touch SQLAlchemy."""
    with (
        patch(_CREATE_ENGINE_PATH) as create_engine_mock,
        _postgres_migration_lock(_SQLITE_URL),
    ):
        pass

    create_engine_mock.assert_not_called()


def test_postgres_url_acquires_and_releases_advisory_lock():
    """Happy path: pg_try_advisory_lock succeeds first try, unlock runs after."""
    engine_mock, conn_mock = _engine_with_conn(scalar_returns=True)

    with (
        patch(_CREATE_ENGINE_PATH, return_value=engine_mock),
        _postgres_migration_lock(_PG_URL),
    ):
        mid_block_calls = _executed_sql(conn_mock).copy()

    all_calls = _executed_sql(conn_mock)

    assert mid_block_calls == [f"SELECT pg_try_advisory_lock({_MIGRATION_ADVISORY_LOCK_ID})"]
    assert all_calls == [
        f"SELECT pg_try_advisory_lock({_MIGRATION_ADVISORY_LOCK_ID})",
        f"SELECT pg_advisory_unlock({_MIGRATION_ADVISORY_LOCK_ID})",
    ]
    engine_mock.dispose.assert_called_once()


def test_postgres_lock_waits_then_acquires_when_another_worker_holds():
    """First try fails (lock held); after polling, second try succeeds."""
    engine_mock, conn_mock = _engine_with_conn(scalar_returns=[False, True])

    with (
        patch(_CREATE_ENGINE_PATH, return_value=engine_mock),
        patch(f"{_SERVICE}.time.sleep") as sleep_mock,
        patch(f"{_SERVICE}.time.monotonic", side_effect=[0.0, 0.0, 1.0]),
        _postgres_migration_lock(_PG_URL),
    ):
        pass

    sql = _executed_sql(conn_mock)
    try_lock = f"SELECT pg_try_advisory_lock({_MIGRATION_ADVISORY_LOCK_ID})"
    assert sql.count(try_lock) == 2, sql
    assert sql[-1] == f"SELECT pg_advisory_unlock({_MIGRATION_ADVISORY_LOCK_ID})"
    sleep_mock.assert_called()  # waited at least one poll interval


def test_postgres_lock_times_out_when_holder_never_releases():
    """If pg_try_advisory_lock never succeeds, raise with an actionable message."""
    engine_mock, conn_mock = _engine_with_conn(scalar_returns=False)

    # monotonic: pre-call once, then once per loop iteration. Deadline crossed quickly.
    with (
        patch(_CREATE_ENGINE_PATH, return_value=engine_mock),
        patch(f"{_SERVICE}.time.sleep"),
        patch(f"{_SERVICE}.time.monotonic", side_effect=[0.0, 0.0, 999.0]),
        pytest.raises(RuntimeError, match="Could not acquire migration advisory lock"),
        _postgres_migration_lock(_PG_URL),
    ):
        pytest.fail("body should not run when lock times out")  # pragma: no cover

    # Engine must still be disposed even after timeout.
    engine_mock.dispose.assert_called_once()
    # And we must not have called pg_advisory_unlock for a lock we never held.
    sql = _executed_sql(conn_mock)
    assert all("pg_advisory_unlock" not in stmt for stmt in sql)


def test_postgres_lock_released_when_block_raises():
    """If the wrapped block raises, the lock must still be released and engine disposed."""
    engine_mock, conn_mock = _engine_with_conn(scalar_returns=True)

    with (
        patch(_CREATE_ENGINE_PATH, return_value=engine_mock),
        pytest.raises(_BoomError),
        _postgres_migration_lock(_PG_URL),
    ):
        raise _BoomError(_BOOM_MESSAGE)

    sql = _executed_sql(conn_mock)
    assert f"SELECT pg_advisory_unlock({_MIGRATION_ADVISORY_LOCK_ID})" in sql
    engine_mock.dispose.assert_called_once()


@pytest.mark.parametrize(
    ("raw_url", "expected_url"),
    [
        ("postgresql+asyncpg://host/db", "postgresql://host/db"),
        ("postgres://host/db", "postgresql://host/db"),
        ("postgresql+psycopg://host/db", "postgresql+psycopg://host/db"),
    ],
)
def test_postgres_url_normalised_to_sync_driver(raw_url: str, expected_url: str):
    """Async driver suffixes must be stripped so create_engine picks a sync driver."""
    engine_mock, _ = _engine_with_conn(scalar_returns=True)

    with (
        patch(_CREATE_ENGINE_PATH, return_value=engine_mock) as create_engine_mock,
        _postgres_migration_lock(raw_url),
    ):
        pass

    create_engine_mock.assert_called_once_with(expected_url)

"""Tests for the schema-migration advisory lock.

Workers booting concurrently against a fresh Postgres race on
``CREATE TYPE`` / ``CREATE TABLE`` because each calls ``alembic upgrade``
independently. ``_postgres_migration_lock`` holds a session-level
``pg_advisory_lock`` for the duration of the upgrade so only one worker
mutates the schema at a time.

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
_CREATE_ENGINE_PATH = "langflow.services.database.service.sa.create_engine"

_BOOM_MESSAGE = "migration exploded"


class _BoomError(RuntimeError):
    """Sentinel exception used to verify the lock releases on failure."""


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
    """Postgres URLs must run pg_advisory_lock before yielding and unlock after."""
    conn_mock = MagicMock()
    engine_mock = MagicMock()
    engine_mock.connect.return_value.__enter__.return_value = conn_mock

    with (
        patch(_CREATE_ENGINE_PATH, return_value=engine_mock),
        _postgres_migration_lock(_PG_URL),
    ):
        mid_block_calls = _executed_sql(conn_mock).copy()

    all_calls = _executed_sql(conn_mock)

    assert mid_block_calls == [f"SELECT pg_advisory_lock({_MIGRATION_ADVISORY_LOCK_ID})"]
    assert all_calls == [
        f"SELECT pg_advisory_lock({_MIGRATION_ADVISORY_LOCK_ID})",
        f"SELECT pg_advisory_unlock({_MIGRATION_ADVISORY_LOCK_ID})",
    ]
    engine_mock.dispose.assert_called_once()


def test_postgres_lock_released_when_block_raises():
    """If the wrapped block raises, the lock must still be released and engine disposed."""
    conn_mock = MagicMock()
    engine_mock = MagicMock()
    engine_mock.connect.return_value.__enter__.return_value = conn_mock

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
    with (
        patch(_CREATE_ENGINE_PATH) as create_engine_mock,
        _postgres_migration_lock(raw_url),
    ):
        create_engine_mock.return_value = MagicMock()

    create_engine_mock.assert_called_once_with(expected_url)

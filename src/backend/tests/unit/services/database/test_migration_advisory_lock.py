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


def test_create_db_and_tables_with_lock_holds_advisory_lock_for_postgres():
    """The locked sync DDL path acquires the lock, runs the DDL, then releases.

    Concurrent workers booting against a fresh PG raced on ``CREATE TYPE``
    inside ``create_db_and_tables`` because the advisory lock previously only
    covered ``run_migrations``. This verifies the new path holds the lock
    around the DDL.
    """
    from langflow.services.database.service import DatabaseService

    lock_engine_mock, lock_conn_mock = _engine_with_conn(scalar_returns=True)
    ddl_engine_mock = MagicMock()
    ddl_conn_mock = MagicMock()
    ddl_engine_mock.begin.return_value.__enter__.return_value = ddl_conn_mock

    service = DatabaseService.__new__(DatabaseService)
    service.database_url = _PG_URL

    create_db_mock = MagicMock()
    with (
        patch(_CREATE_ENGINE_PATH, side_effect=[lock_engine_mock, ddl_engine_mock]) as create_engine_mock,
        patch.object(DatabaseService, "_create_db_and_tables", staticmethod(create_db_mock)),
    ):
        service._create_db_and_tables_with_lock()

    # Two sync engines created: one for the lock, one for the DDL.
    assert create_engine_mock.call_count == 2
    # The DDL ran while the lock was held: unlock is the last call on the lock conn.
    lock_sql = _executed_sql(lock_conn_mock)
    assert lock_sql[0] == f"SELECT pg_try_advisory_lock({_MIGRATION_ADVISORY_LOCK_ID})"
    assert lock_sql[-1] == f"SELECT pg_advisory_unlock({_MIGRATION_ADVISORY_LOCK_ID})"
    # The DDL was passed the DDL engine's connection, not the lock connection.
    create_db_mock.assert_called_once_with(ddl_conn_mock)
    # Both engines disposed even on the happy path.
    lock_engine_mock.dispose.assert_called_once()
    ddl_engine_mock.dispose.assert_called_once()


@pytest.mark.asyncio
async def test_create_db_and_tables_uses_lock_on_postgres():
    """``create_db_and_tables`` dispatches to the locked sync path on Postgres."""
    from langflow.services.database.service import DatabaseService

    service = DatabaseService.__new__(DatabaseService)
    service.database_url = _PG_URL

    with patch.object(DatabaseService, "_create_db_and_tables_with_lock") as locked_mock:
        await service.create_db_and_tables()

    locked_mock.assert_called_once()


@pytest.mark.asyncio
async def test_create_db_and_tables_skips_lock_on_sqlite():
    """SQLite preserves the original async path; the lock helper is never invoked."""
    from langflow.services.database.service import DatabaseService

    service = DatabaseService.__new__(DatabaseService)
    service.database_url = _SQLITE_URL

    async_engine = MagicMock()
    async_conn = MagicMock()

    class _AsyncCM:
        async def __aenter__(self):
            return async_conn

        async def __aexit__(self, *exc):
            return False

    async_engine.begin.return_value = _AsyncCM()
    async_conn.run_sync = MagicMock(return_value=None)

    async def _await_none(*_a, **_kw):
        return None

    async_conn.run_sync = _await_none  # awaited inside create_db_and_tables
    service.engine = async_engine

    with patch.object(DatabaseService, "_create_db_and_tables_with_lock") as locked_mock:
        await service.create_db_and_tables()

    locked_mock.assert_not_called()
    async_engine.begin.assert_called_once()


# ---------------------------------------------------------------------------
# Regression tests for the TOCTOU race in run_migrations (GitHub issue:
# "postgres multi-worker migration race").
#
# Root cause: ``should_initialize_alembic`` was evaluated *before* the
# advisory lock was acquired, so Worker 2 could carry a stale "yes, needs
# init" answer into ``_run_migrations``, try to call ``init_alembic`` on an
# already-migrated DB, and crash when ``command.check()`` detected the
# mismatch.  The fix moves the probe inside the lock so each worker makes its
# decision on fresh data.
# ---------------------------------------------------------------------------


def test_run_migrations_probes_inside_lock_and_skips_init_when_already_migrated():
    """Worker 2 path: _current_alembic_heads_sync returns heads inside the lock.

    After Worker 1 completes the migration, Worker 2 acquires the lock and
    calls ``_current_alembic_heads_sync``.  That probe must return the current
    heads, causing the branch to skip ``init_alembic`` entirely.  Before the
    fix, ``should_initialize_alembic`` was computed outside the lock, so
    Worker 2 always called ``init_alembic`` even when the DB was already
    migrated, crashing on the subsequent ``command.check()``.
    """
    from langflow.services.database.service import DatabaseService

    service = DatabaseService.__new__(DatabaseService)
    service.database_url = _PG_URL

    # Simulate the log buffer path.
    service.alembic_log_to_stdout = True
    service.alembic_log_path = None
    service.script_location = "/fake/script_location"

    engine_mock, conn_mock = _engine_with_conn(scalar_returns=True)  # lock acquired immediately

    init_alembic_mock = MagicMock()
    check_mock = MagicMock()  # command.check succeeds (no diffs detected)

    # _current_alembic_heads_sync returns a non-empty tuple → already migrated.
    heads_mock = MagicMock(return_value=("abc123",))

    with (
        patch(_CREATE_ENGINE_PATH, return_value=engine_mock),
        patch.object(DatabaseService, "init_alembic", staticmethod(init_alembic_mock)),
        patch.object(DatabaseService, "_current_alembic_heads_sync", staticmethod(heads_mock)),
        patch(f"{_SERVICE}.command.check", check_mock),
    ):
        service._run_migrations(fix=False)

    # init_alembic must NOT have been called — the DB was already migrated.
    init_alembic_mock.assert_not_called()
    # The in-lock probe must have been called exactly once.
    heads_mock.assert_called_once()


def test_run_migrations_calls_init_alembic_when_db_is_empty():
    """Worker 1 path: _current_alembic_heads_sync returns () inside the lock.

    When the DB is genuinely empty (fresh deployment), the probe returns an
    empty tuple and ``init_alembic`` must be called.
    """
    from langflow.services.database.service import DatabaseService

    service = DatabaseService.__new__(DatabaseService)
    service.database_url = _PG_URL

    service.alembic_log_to_stdout = True
    service.alembic_log_path = None
    service.script_location = "/fake/script_location"

    engine_mock, _ = _engine_with_conn(scalar_returns=True)

    init_alembic_mock = MagicMock()
    check_mock = MagicMock()

    # Empty DB → _current_alembic_heads_sync returns ().
    heads_mock = MagicMock(return_value=())

    with (
        patch(_CREATE_ENGINE_PATH, return_value=engine_mock),
        patch.object(DatabaseService, "init_alembic", staticmethod(init_alembic_mock)),
        patch.object(DatabaseService, "_current_alembic_heads_sync", staticmethod(heads_mock)),
        patch(f"{_SERVICE}.command.check", check_mock),
    ):
        service._run_migrations(fix=False)

    # init_alembic must have been called exactly once.
    init_alembic_mock.assert_called_once()


def test_concurrent_workers_only_one_calls_init_alembic():
    """Concurrency regression: two threads racing on a fresh DB.

    This is the concrete scenario that caused the original crash.  Before the
    fix, both threads pre-computed ``should_initialize_alembic = True`` outside
    the lock, so both called ``init_alembic`` and the second crashed.

    After the fix the probe is inside the lock.  We simulate this by making
    ``_current_alembic_heads_sync`` return ``()`` only on the *first* call
    (Worker 1 sees an empty DB) and ``("head",)`` on all subsequent calls
    (Worker 2 re-probes inside the lock and finds the already-migrated state).
    Both workers run ``_run_migrations`` concurrently in threads; we assert
    that ``init_alembic`` is called exactly once and neither thread raises.
    """
    import threading

    from langflow.services.database.service import DatabaseService

    service = DatabaseService.__new__(DatabaseService)
    service.database_url = _PG_URL
    service.alembic_log_to_stdout = True
    service.alembic_log_path = None
    service.script_location = "/fake/script_location"

    # Alternate lock acquisition: first call acquires, second polls once then acquires.
    lock_engine_1, _ = _engine_with_conn(scalar_returns=True)
    lock_engine_2, _ = _engine_with_conn(scalar_returns=True)
    lock_engines = iter([lock_engine_1, lock_engine_2])

    init_alembic_call_count = 0
    init_alembic_lock = threading.Lock()

    def _init_alembic(cfg):
        nonlocal init_alembic_call_count
        with init_alembic_lock:
            init_alembic_call_count += 1

    # First call returns () (empty DB); all subsequent calls return a head.
    heads_call_count = 0
    heads_lock = threading.Lock()

    def _heads_probe(cfg):
        nonlocal heads_call_count
        with heads_lock:
            heads_call_count += 1
            if heads_call_count == 1:
                return ()  # Worker 1 sees empty DB
            return ("head_abc",)  # Worker 2 sees already-migrated DB

    errors: list[Exception] = []

    def _run(fix=False):
        try:
            service._run_migrations(fix=fix)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    check_mock = MagicMock()

    with (
        patch(_CREATE_ENGINE_PATH, side_effect=lock_engines),
        patch.object(DatabaseService, "init_alembic", staticmethod(_init_alembic)),
        patch.object(DatabaseService, "_current_alembic_heads_sync", staticmethod(_heads_probe)),
        patch(f"{_SERVICE}.command.check", check_mock),
    ):
        t1 = threading.Thread(target=_run)
        t2 = threading.Thread(target=_run)
        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)

    assert not errors, f"Worker(s) raised: {errors}"
    assert init_alembic_call_count == 1, (
        f"Expected init_alembic to be called exactly once; called {init_alembic_call_count} times. "
        "This is the TOCTOU race: both workers decided to initialise before the fix."
    )

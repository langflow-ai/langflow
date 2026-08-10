"""Tests for the schema-migration locks.

Workers booting concurrently race on ``CREATE TYPE`` / ``CREATE TABLE`` and on
``alembic upgrade`` because each one runs them independently. Two locks keep
that serialised: ``_postgres_migration_lock`` holds a session-level
``pg_advisory_lock``, and ``_sqlite_migration_lock`` holds a
``filelock.FileLock`` next to the ``.db`` file.

The Postgres lock is acquired via ``pg_try_advisory_lock`` in a bounded polling
loop so a hung holder can't block every other worker forever; the wait emits a
log line and times out with an actionable error.

Mocking ``sa.create_engine`` for the Postgres cases so they run without a real
Postgres instance. The unit under test there is the orchestration: which SQL
gets executed, in what order, on which kinds of URLs. The SQLite lock needs no
mocking - it is a real file lock on a tmp_path.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import sqlalchemy as sa
from langflow.services.database import service as database_service_module
from langflow.services.database.service import (
    _MIGRATION_ADVISORY_LOCK_ID,
    _MIGRATION_LOCK_DEFAULT_TIMEOUT_S,
    DatabaseService,
    _migration_lock_timeout_s,
    _normalize_sync_postgres_url,
    _postgres_migration_lock,
    _sqlite_migration_lock,
)
from sqlalchemy.ext.asyncio import create_async_engine
from tenacity import wait_none

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


@pytest.mark.parametrize(
    "database_url",
    [_SQLITE_URL, "postgresqlproxy+asyncpg://host/db"],
    ids=["sqlite", "postgres-prefix-plugin"],
)
def test_non_postgres_url_is_a_noop_no_engine_created(database_url):
    """Other backends must not be mistaken for Postgres advisory-lock targets."""
    with (
        patch(_CREATE_ENGINE_PATH) as create_engine_mock,
        _postgres_migration_lock(database_url),
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


def test_aiosqlite_none_filename_is_normalised_to_the_same_sync_target():
    assert _normalize_sync_postgres_url("sqlite+aiosqlite://?uri=true") == "sqlite:///None?uri=true"


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


def test_sqlite_locked_ddl_preserves_configured_connect_args(tmp_path):
    """The sync SQLite DDL engine keeps the configured driver options."""
    service = DatabaseService.__new__(DatabaseService)
    db_path = tmp_path / "langflow+aiosqlite.db"
    service.database_url = f"sqlite+aiosqlite:///{db_path}"
    connect_args = {"check_same_thread": False, "timeout": 12.5}
    service._get_connect_args = MagicMock(return_value=connect_args)

    ddl_engine_mock = MagicMock()
    ddl_conn_mock = ddl_engine_mock.begin.return_value.__enter__.return_value
    create_db_mock = MagicMock()
    with (
        patch(_CREATE_ENGINE_PATH, return_value=ddl_engine_mock) as create_engine_mock,
        patch.object(DatabaseService, "_create_db_and_tables", staticmethod(create_db_mock)),
    ):
        service._create_db_and_tables_with_lock()

    create_engine_mock.assert_called_once_with(f"sqlite:///{db_path}", connect_args=connect_args)
    create_db_mock.assert_called_once_with(ddl_conn_mock)


def test_sqlite_locked_ddl_filters_aiosqlite_only_connect_args(tmp_path):
    """The sync DDL engine must not receive options consumed by aiosqlite itself."""
    service = DatabaseService.__new__(DatabaseService)
    db_path = tmp_path / "langflow.db"
    service.database_url = f"sqlite+aiosqlite:///{db_path}"
    service._get_connect_args = MagicMock(
        return_value={
            "check_same_thread": False,
            "timeout": 12.5,
            "iter_chunk_size": 128,
            "loop": None,
        }
    )

    metadata = sa.MetaData()
    sa.Table("migration_probe", metadata, sa.Column("id", sa.Integer, primary_key=True))
    with patch.object(
        DatabaseService,
        "_create_db_and_tables",
        staticmethod(lambda connection: metadata.create_all(connection)),
    ):
        service._create_db_and_tables_with_lock()

    verification_engine = sa.create_engine(f"sqlite:///{db_path}")
    try:
        with verification_engine.connect() as connection:
            assert sa.inspect(connection).has_table("migration_probe")
    finally:
        verification_engine.dispose()


@pytest.mark.asyncio
async def test_create_db_and_tables_uses_lock_on_postgres():
    """``create_db_and_tables`` dispatches to the locked sync path on Postgres."""
    from langflow.services.database.service import DatabaseService

    service = DatabaseService.__new__(DatabaseService)
    service.database_url = _PG_URL

    with patch.object(DatabaseService, "_create_db_and_tables_with_lock") as locked_mock:
        await service.create_db_and_tables()

    locked_mock.assert_called_once()


@pytest.mark.parametrize(
    "database_url",
    [
        "mysql+aiomysql://host/db",
        "sqlitecloud+aiosqlite://host/db",
        "postgresqlproxy+asyncpg://host/db",
    ],
    ids=["mysql", "sqlite-prefix-plugin", "postgres-prefix-plugin"],
)
@pytest.mark.asyncio
async def test_create_db_and_tables_preserves_async_path_for_other_dialects(database_url):
    """Non-Postgres dialects must not be handed to a synchronous engine."""
    service = DatabaseService.__new__(DatabaseService)
    service.database_url = database_url
    connection_mock = MagicMock()
    connection_mock.run_sync = AsyncMock()
    service.engine = MagicMock()
    service.engine.begin.return_value.__aenter__.return_value = connection_mock

    with patch.object(DatabaseService, "_create_db_and_tables_with_lock") as locked_mock:
        await service.create_db_and_tables()

    locked_mock.assert_not_called()
    connection_mock.run_sync.assert_awaited_once_with(service._create_db_and_tables)


@pytest.mark.asyncio
async def test_create_db_and_tables_retry_does_not_repeat_lock_timeout(monkeypatch):
    """A bounded lock wait must not be multiplied by the connection retry."""
    service = DatabaseService.__new__(DatabaseService)
    lock_timeout_type = getattr(database_service_module, "MigrationLockTimeoutError", RuntimeError)
    create_db_mock = AsyncMock(
        side_effect=lock_timeout_type("Could not acquire SQLite migration file lock within 300s")
    )
    service.create_db_and_tables = create_db_mock
    monkeypatch.setattr(DatabaseService.create_db_and_tables_with_retry.retry, "wait", wait_none())

    with pytest.raises(lock_timeout_type, match="Could not acquire SQLite migration file lock"):
        await service.create_db_and_tables_with_retry()

    create_db_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_db_and_tables_retry_does_not_repeat_cancellation(monkeypatch):
    """Cancellation must propagate immediately instead of becoming a retry error."""
    service = DatabaseService.__new__(DatabaseService)
    create_db_mock = AsyncMock(side_effect=asyncio.CancelledError)
    service.create_db_and_tables = create_db_mock
    monkeypatch.setattr(DatabaseService.create_db_and_tables_with_retry.retry, "wait", wait_none())

    with pytest.raises(asyncio.CancelledError):
        await service.create_db_and_tables_with_retry()

    create_db_mock.assert_awaited_once()


@pytest.mark.parametrize(
    "database_url",
    [
        _SQLITE_URL,
        "sqlite+aiosqlite:///relative.db?mode=memory&uri=true",
        "sqlite+aiosqlite:///:memory:?mode=memory&cache=shared&uri=true",
        "sqlite+aiosqlite:///?mode=memory&uri=true",
        "sqlite+aiosqlite://?uri=true",
        "sqlite+aiosqlite:///file:upper-mode.db?Mode=memory&uri=true",
        "sqlite+aiosqlite:///file:encoded-upper-mode.db?%254Dode=memory&uri=true",
        "sqlite+aiosqlite:///file:mode-override.db?%256dode=memory&mode=rwc&uri=true",
        "sqlite+aiosqlite:///file:vfs-override.db?%2576fs=memdb&vfs=unix&uri=true",
        "sqlite+aiosqlite:///file:tab-mode.db?mo%09de=memory&uri=true",
        "sqlite+aiosqlite:///file:cr-mode.db?mo%0Dde=memory&uri=true",
        "sqlite+aiosqlite:///file:lf-vfs.db?v%0Afs=memdb&uri=true",
        "sqlite+aiosqlite:///file:path\tname.db?uri=true",
    ],
    ids=[
        "ordinary-file",
        "non-file-uri-name",
        "memory-marker-uri-name",
        "empty-uri-name",
        "none-uri-name",
        "case-sensitive-mode",
        "encoded-case-sensitive-mode",
        "decoded-mode-last-value",
        "decoded-vfs-last-value",
        "tab-in-mode-key",
        "carriage-return-in-mode-key",
        "newline-in-vfs-key",
        "tab-in-path",
    ],
)
@pytest.mark.asyncio
async def test_create_db_and_tables_takes_lock_on_sqlite(database_url):
    """SQLite runs the DDL under the lock too.

    Workers booting concurrently against one SQLite file race on
    ``table.create(checkfirst=True)`` and the losers fail with
    ``database is locked``, so the file lock has to cover this path as well
    and not just ``run_migrations``.
    """
    from langflow.services.database.service import DatabaseService

    service = DatabaseService.__new__(DatabaseService)
    service.database_url = database_url

    with patch.object(DatabaseService, "_create_db_and_tables_with_lock") as locked_mock:
        await service.create_db_and_tables()

    locked_mock.assert_called_once()


@pytest.mark.parametrize(
    "database_url",
    [
        "sqlite+aiosqlite://",
        "sqlite+aiosqlite:///:memory:",
        "sqlite+aiosqlite:///file::memory:?cache=shared&uri=true",
        "sqlite+aiosqlite:///file:memdb1?mode=memory&cache=shared&uri=true",
        "sqlite+aiosqlite:///file:memdb2?mode=memory&cache=shared&uri=1",
        "sqlite+aiosqlite:///file:memdup?mode=memory&cache=shared&uri=false&uri=false",
        "sqlite+aiosqlite:///file:memdb-vfs?vfs=memdb&uri=true",
        "sqlite+aiosqlite:///file:%3Amemory%3A?uri=true",
        "sqlite+aiosqlite:///file:%3amemory%3a?uri=true",
        "sqlite+aiosqlite:///file:encoded-mode?mode=%256demory&uri=true",
        "sqlite+aiosqlite:///file:encoded-vfs?vfs=%256demdb&uri=true",
        "sqlite+aiosqlite:///file:encoded-mode-key?%256dode=memory&uri=true",
        "sqlite+aiosqlite:///file:encoded-vfs-key?%2576fs=memdb&uri=true",
        "sqlite+aiosqlite:///file:delimited-mode?x=%26mode%3Dmemory&uri=true",
        "sqlite+aiosqlite:///file:delimited-vfs?x=%26vfs%3Dmemdb&uri=true",
        "sqlite+aiosqlite:///file:fragment-mode?mode=memory%23ignored&uri=true",
        "sqlite+aiosqlite:///file:nul-mode?mode%2500suffix=memory&uri=true",
        "sqlite+aiosqlite:///file:%3Amemory%3A%00suffix?uri=true",
    ],
    ids=[
        "fileless",
        "memory-marker",
        "uri-memory",
        "named-uri-memory",
        "truthy-uri-memory",
        "duplicate-uri-memory",
        "vfs-uri-memory",
        "encoded-uri-memory",
        "lowercase-encoded-uri-memory",
        "encoded-mode-uri-memory",
        "encoded-vfs-uri-memory",
        "encoded-mode-key-uri-memory",
        "encoded-vfs-key-uri-memory",
        "delimited-mode-uri-memory",
        "delimited-vfs-uri-memory",
        "fragment-mode-uri-memory",
        "nul-mode-uri-memory",
        "nul-path-uri-memory",
    ],
)
@pytest.mark.asyncio
async def test_create_db_and_tables_populates_application_engine_for_in_memory_sqlite(
    database_url,
    tmp_path,
    monkeypatch,
):
    """Fileless SQLite tables must live on the application's own engine."""
    monkeypatch.chdir(tmp_path)
    service = DatabaseService.__new__(DatabaseService)
    service.database_url = database_url
    service.engine = create_async_engine(database_url)
    service._get_connect_args = MagicMock(return_value={"uri": True})

    try:
        await service.create_db_and_tables()
        async with service.engine.connect() as conn:
            table_names = await conn.run_sync(lambda sync_conn: sa.inspect(sync_conn).get_table_names())
        assert "flow" in table_names
    finally:
        await service.engine.dispose()


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("-1", _MIGRATION_LOCK_DEFAULT_TIMEOUT_S),
        ("nan", _MIGRATION_LOCK_DEFAULT_TIMEOUT_S),
        ("inf", _MIGRATION_LOCK_DEFAULT_TIMEOUT_S),
        ("-inf", _MIGRATION_LOCK_DEFAULT_TIMEOUT_S),
        ("0", 0.0),
    ],
)
def test_migration_lock_timeout_is_finite_and_non_negative(monkeypatch, raw, expected):
    monkeypatch.setenv("LANGFLOW_MIGRATION_LOCK_TIMEOUT_S", raw)

    assert _migration_lock_timeout_s() == expected


def test_sqlite_migration_lock_is_a_noop_without_a_file(tmp_path):
    """In-memory SQLite has no file to lock, so the lock must not create one."""
    with _sqlite_migration_lock("sqlite:///:memory:"):
        pass

    assert list(tmp_path.iterdir()) == []


def test_sqlite_migration_lock_serialises_and_releases(tmp_path, monkeypatch):
    """A real file lock: held for the block, refused while held, reusable after.

    This is the whole point of the lock, so it uses a real ``FileLock`` on a
    real path rather than mocks. The timeout is dialled down so the contended
    case fails fast instead of waiting the 300s default.
    """
    monkeypatch.setenv("LANGFLOW_MIGRATION_LOCK_TIMEOUT_S", "0.1")
    url = f"sqlite:///{tmp_path}/langflow.db"
    # Suffix appended, not replaced, so the existing ``*.db*`` gitignore rule
    # keeps the lock file out of commits.
    lock_file = tmp_path / "langflow.db.migration.lock"

    with _sqlite_migration_lock(url):
        assert lock_file.exists()
        # A second holder cannot get in while the first is inside the block.
        with (
            pytest.raises(RuntimeError, match="Could not acquire SQLite migration file lock"),
            _sqlite_migration_lock(url),
        ):
            pytest.fail("second holder must not enter while the lock is held")

    # Released on exit, so the next worker gets through.
    with _sqlite_migration_lock(url):
        pass


def test_sqlite_migration_lock_releases_when_block_raises(tmp_path, monkeypatch):
    """A migration that blows up must not leave the lock held for everyone else."""
    monkeypatch.setenv("LANGFLOW_MIGRATION_LOCK_TIMEOUT_S", "0.1")
    url = f"sqlite:///{tmp_path}/langflow.db"

    with pytest.raises(_BoomError), _sqlite_migration_lock(url):
        raise _BoomError(_BOOM_MESSAGE)

    with _sqlite_migration_lock(url):
        pass

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from langflow.services.database.revision import (
    LEGACY_BRANCH_POINT,
    LEGACY_REVISIONS,
    DatabaseRevisionError,
    classify_revisions,
    read_revisions_before_startup,
    script_directory,
)
from langflow.services.database.service import DatabaseService
from langflow.services.database.utils import initialize_database
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine


@pytest.mark.parametrize("revision", sorted(LEGACY_REVISIONS))
def test_known_1_10_3_side_branches_have_an_explicit_upgrade_route(revision):
    state = classify_revisions({revision})

    assert state.kind == "legacy"
    assert state.upgrade_from == LEGACY_BRANCH_POINT


def test_normal_revisions_and_a_fresh_database_are_supported():
    script = script_directory()
    assert classify_revisions(set()).kind == "known"
    assert classify_revisions(set(script.get_heads())).kind == "known"
    assert classify_revisions({LEGACY_BRANCH_POINT}).kind == "known"


def test_upgrade_qa_and_release_histories_have_one_common_head():
    script = script_directory()
    ancestry = {revision.revision for revision in script.iterate_revisions(script.get_current_head(), "base")}
    assert {"3d7f9a1c5e80", "9b1d3f5a7c8e", "f6a2c8e4b901"} <= ancestry  # pragma: allowlist secret


@pytest.mark.parametrize(
    "revisions",
    [
        {"unknown_future_revision"},
        {"unknown_future_revision", LEGACY_BRANCH_POINT},
        {"d49cbced8696", LEGACY_BRANCH_POINT},
        {"d49cbced8696", "90c977dcf0f1"},
        {"head"},
        {""},
        {LEGACY_BRANCH_POINT[:8]},
    ],
)
def test_unknown_or_mixed_side_branch_revisions_are_refused(revisions):
    state = classify_revisions(revisions)

    assert state.kind == "unknown"
    with pytest.raises(DatabaseRevisionError, match="restore"):
        state.require_supported()


def test_overlapping_known_revisions_are_refused():
    head = script_directory().get_current_head()
    state = classify_revisions({head, LEGACY_BRANCH_POINT})

    assert state.kind == "unknown"
    assert "overlap" in state.message


def _service(database: Path, *, uri_mode: str | None = None, mode: str | None = None) -> DatabaseService:
    service = object.__new__(DatabaseService)
    service.database_url = f"sqlite+aiosqlite:///{database}"
    query = []
    if uri_mode is not None:
        query.append(f"uri={uri_mode}")
    if mode is not None:
        query.append(f"mode={mode}")
    if query:
        service.database_url += "?" + "&".join(query)
    service.engine = create_async_engine(service.database_url)
    service.script_location = Path(__import__("langflow").__file__).parent / "alembic"
    service.settings_service = SimpleNamespace(settings=SimpleNamespace(database_connection_retry=False))
    return service


def _record_revision(database: Path, revision: str) -> None:
    with sqlite3.connect(database.resolve()) as connection:
        connection.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) PRIMARY KEY)")
        connection.execute("INSERT INTO alembic_version VALUES (?)", (revision,))


@pytest.mark.parametrize("uri_mode", [None, "false", "0"])
@pytest.mark.parametrize("decoy_exists", [False, True])
@pytest.mark.skipif(sys.platform == "win32", reason="Windows cannot represent this literal colon filename")
async def test_literal_file_prefix_checks_the_engine_database_before_startup(
    tmp_path, monkeypatch, uri_mode, decoy_exists
):
    monkeypatch.chdir(tmp_path)
    database = Path("file:source.db")
    _record_revision(database, "unknown_future_revision")
    if decoy_exists:
        _record_revision(Path("source.db"), LEGACY_BRANCH_POINT)
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir()}
    service = _service(database, uri_mode=uri_mode)
    service.ensure_postgresql_version = AsyncMock()
    service.create_db_and_tables = AsyncMock(side_effect=AssertionError("must not create tables"))
    monkeypatch.setattr("langflow.services.deps.get_db_service", lambda: service)
    try:
        with pytest.raises(DatabaseRevisionError, match="unknown_future_revision"):
            await initialize_database()
        assert {path.name: path.read_bytes() for path in tmp_path.iterdir()} == before
        service.create_db_and_tables.assert_not_awaited()
    finally:
        await service.engine.dispose()


@pytest.mark.parametrize("uri_mode", ["true", "1"])
async def test_uri_file_prefix_checks_the_decoded_database(tmp_path, monkeypatch, uri_mode):
    monkeypatch.chdir(tmp_path)
    database = Path("source file.db")
    _record_revision(database, "unknown_future_revision")
    service = _service(Path("file:source%20file.db"), uri_mode=uri_mode)
    try:
        assert await read_revisions_before_startup(service.engine) == {"unknown_future_revision"}
    finally:
        await service.engine.dispose()


@pytest.mark.parametrize("uri_mode", ["true", "1"])
@pytest.mark.parametrize("mode", ["ro", "memory"])
@pytest.mark.parametrize("decoy_exists", [False, True])
@pytest.mark.skipif(sys.platform == "win32", reason="Windows cannot represent this literal question-mark filename")
async def test_uri_flag_without_file_prefix_checks_the_complete_literal_filename(
    tmp_path, monkeypatch, uri_mode, mode, decoy_exists
):
    monkeypatch.chdir(tmp_path)
    database = Path(f"source.db?mode={mode}")
    _record_revision(database, "unknown_future_revision")
    if decoy_exists:
        _record_revision(Path("source.db"), LEGACY_BRANCH_POINT)
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir()}
    service = _service(Path("source.db"), uri_mode=uri_mode, mode=mode)
    arguments, _ = service.engine.dialect.create_connect_args(service.engine.url)
    assert Path(arguments[0]) == database
    application_connections = []
    event.listen(service.engine.sync_engine, "connect", lambda *_: application_connections.append(True))
    service.ensure_postgresql_version = AsyncMock()
    service.create_db_and_tables = AsyncMock(side_effect=AssertionError("must not create tables"))
    monkeypatch.setattr("langflow.services.deps.get_db_service", lambda: service)
    try:
        with pytest.raises(DatabaseRevisionError, match="unknown_future_revision"):
            await initialize_database()
        assert application_connections == []
        assert {path.name: path.read_bytes() for path in tmp_path.iterdir()} == before
        service.create_db_and_tables.assert_not_awaited()
    finally:
        await service.engine.dispose()


@pytest.mark.parametrize("uri_mode", ["true", "1"])
@pytest.mark.skipif(sys.platform == "win32", reason="Windows cannot represent this literal question-mark filename")
async def test_uri_memory_query_without_file_prefix_does_not_create_a_missing_file(tmp_path, monkeypatch, uri_mode):
    monkeypatch.chdir(tmp_path)
    service = _service(Path("missing.db"), uri_mode=uri_mode, mode="memory")
    application_connections = []
    event.listen(service.engine.sync_engine, "connect", lambda *_: application_connections.append(True))
    try:
        assert await read_revisions_before_startup(service.engine) == set()
        assert application_connections == []
        assert not list(tmp_path.iterdir())
    finally:
        await service.engine.dispose()


@pytest.mark.skipif(sys.platform == "win32", reason="Windows cannot represent this literal colon filename")
async def test_file_memory_name_is_literal_without_uri_mode(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    database = Path("file::memory:")
    _record_revision(database, "unknown_future_revision")
    before = database.read_bytes()
    service = _service(database)
    event.listen(service.engine.sync_engine, "connect", lambda conn, _: conn.execute("PRAGMA journal_mode=WAL"))
    try:
        assert await read_revisions_before_startup(service.engine) == {"unknown_future_revision"}
        assert database.read_bytes() == before
        assert {path.name for path in tmp_path.iterdir()} == {database.name}
    finally:
        await service.engine.dispose()


async def test_ignored_memory_query_does_not_create_a_missing_literal_database(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    engine = create_async_engine("sqlite+aiosqlite:///missing.db?mode=memory")
    try:
        assert await read_revisions_before_startup(engine) == set()
        assert not list(tmp_path.iterdir())
    finally:
        await engine.dispose()


@pytest.mark.parametrize("database", [":memory:", "file::memory:", "file:shared-memory?mode=memory"])
async def test_actual_memory_database_uses_the_existing_engine(tmp_path, monkeypatch, database):
    monkeypatch.chdir(tmp_path)
    separator = "&" if "?" in database else "?"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database}{separator}uri=true")
    try:
        async with engine.begin() as connection:
            await connection.exec_driver_sql("CREATE TABLE alembic_version (version_num VARCHAR(32) PRIMARY KEY)")
            await connection.exec_driver_sql("INSERT INTO alembic_version VALUES ('unknown_future_revision')")
        assert await read_revisions_before_startup(engine) == {"unknown_future_revision"}
        assert not list(tmp_path.iterdir())
    finally:
        await engine.dispose()


@pytest.mark.parametrize("entry", ["startup", "migrations"])
@pytest.mark.parametrize(
    "revisions", [("unknown_future_revision",), (LEGACY_BRANCH_POINT, script_directory().get_current_head())]
)
async def test_an_unknown_database_is_rejected_before_any_schema_or_data_changes(
    tmp_path, monkeypatch, entry, revisions
):
    database = tmp_path / "future.db"
    with sqlite3.connect(database) as connection:
        connection.executescript(
            "CREATE TABLE alembic_version (version_num VARCHAR(32) PRIMARY KEY);"
            "CREATE TABLE customer_data (value TEXT);"
            "INSERT INTO customer_data VALUES ('preserve me');"
        )
        connection.executemany("INSERT INTO alembic_version VALUES (?)", [(revision,) for revision in revisions])
    before = database.read_bytes()
    service = _service(database)
    event.listen(service.engine.sync_engine, "connect", lambda conn, _: conn.execute("PRAGMA journal_mode=WAL"))
    service.ensure_postgresql_version = AsyncMock()
    service.create_db_and_tables = AsyncMock(side_effect=AssertionError("must not create tables"))
    monkeypatch.setattr("langflow.services.deps.get_db_service", lambda: service)
    operation = initialize_database if entry == "startup" else service.run_migrations

    try:
        with pytest.raises(DatabaseRevisionError, match="restore"):
            await operation()
        assert database.read_bytes() == before
        assert not list(tmp_path.glob("future.db-*"))
    finally:
        await service.engine.dispose()


async def test_refused_startup_teardown_never_opens_an_application_connection(tmp_path, monkeypatch):
    from langflow.services import utils
    from lfx.services.manager import get_service_manager
    from lfx.services.schema import ServiceType
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from sqlmodel.ext.asyncio.session import AsyncSession

    database = tmp_path / "future.db"
    _record_revision(database, "unknown_future_revision")
    before = database.read_bytes()
    service = _service(database)
    service.settings_service.settings.use_noop_database = False
    service.async_session_maker = async_sessionmaker(service.engine, class_=AsyncSession, expire_on_commit=False)
    service.ensure_postgresql_version = AsyncMock()
    cleanup = AsyncMock(side_effect=AssertionError("refused startup must not change users"))
    monkeypatch.setattr(utils, "teardown_superuser", cleanup)
    monkeypatch.setattr("langflow.services.deps.get_db_service", lambda: service)
    manager = get_service_manager()
    monkeypatch.setattr(manager, "services", {ServiceType.DATABASE_SERVICE: service})
    event.listen(service.engine.sync_engine, "connect", lambda *_: pytest.fail("refusal cleanup opened the database"))
    with pytest.raises(DatabaseRevisionError):
        await initialize_database()
    await utils.teardown_services()
    assert database.read_bytes() == before
    assert not list(tmp_path.glob("future.db-*"))
    cleanup.assert_not_awaited()

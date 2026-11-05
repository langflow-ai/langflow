from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from langflow.services.database.revision import (
    LEGACY_BRANCH_POINT,
    LEGACY_REVISIONS,
    DatabaseRevisionError,
    classify_revisions,
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


def _service(database: Path) -> DatabaseService:
    service = object.__new__(DatabaseService)
    service.database_url = f"sqlite+aiosqlite:///{database}"
    service.engine = create_async_engine(service.database_url)
    service.script_location = Path(__import__("langflow").__file__).parent / "alembic"
    service.settings_service = SimpleNamespace(settings=SimpleNamespace(database_connection_retry=False))
    return service


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

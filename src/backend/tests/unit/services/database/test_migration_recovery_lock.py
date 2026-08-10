from __future__ import annotations

from contextlib import asynccontextmanager, contextmanager, nullcontext
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from alembic import util
from langflow.services import deps
from langflow.services.database import service as database_service_module
from langflow.services.database import utils as database_utils
from langflow.services.database.service import DatabaseService

_MISSING_REVISION_ERROR = "Can't locate revision identified by 'missing'"
_NOT_UP_TO_DATE_ERROR = "Target database is not up to date"


def test_invalid_revision_recovery_stays_inside_migration_lock(monkeypatch):
    service = DatabaseService.__new__(DatabaseService)
    service.database_url = "sqlite+aiosqlite:///./langflow.db"
    service.script_location = Path("/installed/langflow/alembic")
    service._open_alembic_log_buffer = lambda: nullcontext(StringIO())

    events: list[str] = []
    revision_state = "bad"

    @contextmanager
    def sqlite_lock(_database_url):
        events.append("lock-enter")
        try:
            yield
        finally:
            events.append("lock-exit")

    def check(_alembic_cfg):
        events.append(f"check-{revision_state}")
        if revision_state == "bad":
            raise util.CommandError(_MISSING_REVISION_ERROR)
        if revision_state == "base":
            raise util.CommandError(_NOT_UP_TO_DATE_ERROR)

    def upgrade(_alembic_cfg, revision):
        nonlocal revision_state
        events.append(f"upgrade-{revision_state}-{revision}")
        if revision_state == "bad":
            raise util.CommandError(_MISSING_REVISION_ERROR)
        revision_state = "head"

    def stamp(_alembic_cfg, revision, *, purge):
        nonlocal revision_state
        assert revision == "base"
        assert purge is True
        events.append("stamp-base")
        revision_state = "base"

    monkeypatch.setattr(database_service_module, "_sqlite_migration_lock", sqlite_lock)
    monkeypatch.setattr(database_service_module, "_postgres_migration_lock", lambda _url: nullcontext())
    monkeypatch.setattr(database_service_module.command, "check", check)
    monkeypatch.setattr(database_service_module.command, "upgrade", upgrade)
    monkeypatch.setattr(database_service_module.command, "stamp", stamp)
    monkeypatch.setattr(database_service_module.time, "sleep", lambda _seconds: None)

    # Simulate two workers that both observed the stale revision before waiting.
    # The second must re-check after the first repairs it and must not purge again.
    service._run_migrations(should_initialize_alembic=False, fix=False)
    service._run_migrations(should_initialize_alembic=False, fix=False)

    assert events == [
        "lock-enter",
        "check-bad",
        "upgrade-bad-head",
        "stamp-base",
        "check-base",
        "upgrade-base-head",
        "check-head",
        "lock-exit",
        "lock-enter",
        "check-head",
        "check-head",
        "lock-exit",
    ]


@pytest.mark.asyncio
async def test_initialize_database_never_drops_revision_table_outside_service_lock(monkeypatch):
    database_service = SimpleNamespace(
        database_url="sqlite+aiosqlite:///:memory:",
        settings_service=SimpleNamespace(settings=SimpleNamespace(database_connection_retry=False)),
        ensure_postgresql_version=AsyncMock(),
        create_db_and_tables=AsyncMock(),
        check_schema_health=AsyncMock(),
        run_migrations=AsyncMock(side_effect=util.CommandError(_MISSING_REVISION_ERROR)),
    )

    @asynccontextmanager
    async def forbidden_session_scope():
        pytest.fail("alembic_version recovery must not run outside the migration lock")
        yield  # pragma: no cover

    monkeypatch.setattr(deps, "get_db_service", lambda: database_service)
    monkeypatch.setattr(deps, "session_scope", forbidden_session_scope)

    with pytest.raises(util.CommandError, match="Can't locate revision"):
        await database_utils.initialize_database()

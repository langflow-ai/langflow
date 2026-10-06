"""API fixture optimizations must preserve data isolation and real startup coverage."""

from importlib import import_module
from types import SimpleNamespace

import pytest
from filelock import FileLock
from langflow.initial_setup.constants import STARTER_FOLDER_NAME
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.service import DatabaseService
from langflow.services.deps import session_scope
from sqlmodel import select, text


@pytest.mark.parametrize("iteration", range(2))
async def test_client_schema_and_rows_are_isolated(client, iteration):  # noqa: ARG001
    async with session_scope() as session:
        existing = await session.exec(text("SELECT name FROM sqlite_master WHERE name='fixture_isolation_probe'"))
        assert existing.first() is None
        await session.exec(text("CREATE TABLE fixture_isolation_probe (value INTEGER)"))
        await session.exec(text("INSERT INTO fixture_isolation_probe VALUES (1)"))


@pytest.fixture
def migration_calls(monkeypatch):
    calls = []
    original = DatabaseService.run_migrations

    async def record(service, *, fix=False):
        calls.append(service.database_url)
        return await original(service, fix=fix)

    monkeypatch.setattr(DatabaseService, "run_migrations", record)
    return calls


@pytest.fixture
async def counted_client(migration_calls, client):
    return client, migration_calls


@pytest.mark.full_database_init
@pytest.mark.parametrize("iteration", range(2))
async def test_full_initialization_runs_migrations_each_time(counted_client, iteration):  # noqa: ARG001
    _, calls = counted_client
    assert len(calls) == 1


@pytest.fixture
def occupied_startup_lock(tmp_path, monkeypatch):
    # Simulate another app holding the process-wide starter-project lock, without
    # interfering with unrelated tests running on other workers.
    main = import_module("langflow.main")
    monkeypatch.setattr(main, "tempfile", SimpleNamespace(gettempdir=lambda: str(tmp_path)))
    with FileLock(tmp_path / "langflow_starter_projects.lock", timeout=5):
        yield


@pytest.fixture
async def client_with_occupied_startup_lock(occupied_startup_lock, client):  # noqa: ARG001
    return client


async def test_client_seeds_starters_while_another_database_starts(client_with_occupied_startup_lock):  # noqa: ARG001
    async with session_scope() as session:
        starter = (
            await session.exec(select(Folder).where(Folder.name == STARTER_FOLDER_NAME, Folder.user_id.is_(None)))
        ).first()
    assert starter is not None

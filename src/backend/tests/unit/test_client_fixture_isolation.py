"""API fixture optimizations must preserve data isolation and real startup coverage."""

import pytest
from langflow.services.database.service import DatabaseService
from langflow.services.deps import session_scope
from sqlmodel import text


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

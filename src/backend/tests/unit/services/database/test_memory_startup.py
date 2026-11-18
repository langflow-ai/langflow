from __future__ import annotations

from types import SimpleNamespace

import pytest
from langflow.services.database.models.vertex_builds.model import VertexBuildTable  # noqa: F401
from langflow.services.database.revision import DatabaseRevisionError, read_revisions_before_startup, script_directory
from langflow.services.database.service import DatabaseService
from langflow.services.database.utils import initialize_database
from lfx.services.settings.base import Settings
from sqlalchemy import event, inspect, text
from sqlalchemy.engine import Engine


@pytest.fixture
def memory_service(tmp_path, request):
    settings = Settings.model_construct(
        database_url=request.param,
        config_dir=str(tmp_path),
        alembic_log_to_stdout=True,
    )
    service = DatabaseService(SimpleNamespace(settings=settings))
    yield service
    event.remove(Engine, "connect", service.on_connection)


@pytest.mark.parametrize(
    "memory_service",
    [
        "sqlite://",
        "sqlite:///:memory:",
        "sqlite+aiosqlite:///file::memory:?uri=true",
        "sqlite+aiosqlite:///file:%3Amemory%3A?uri=true",
        "sqlite+aiosqlite:///file:startup-test?mode=memory&uri=true",
    ],
    indirect=True,
)
async def test_memory_database_initializes_with_default_settings(memory_service, monkeypatch):
    monkeypatch.setattr("langflow.services.deps.get_db_service", lambda: memory_service)
    try:
        await initialize_database()
        assert memory_service.database_initialized
        assert await read_revisions_before_startup(memory_service.engine) == set(script_directory().get_heads())
        async with memory_service.engine.begin() as connection:
            tables = await connection.run_sync(lambda sync: inspect(sync).get_table_names())
            assert {"flow", "user", "worker_registry", "alembic_version"} <= set(tables)
            assert (await connection.execute(text("SELECT count(*) FROM authz_role"))).scalar_one() >= 3
        for scope in (
            memory_service.session_scope_for_heartbeat,
            memory_service.session_scope_for_sync_validation,
        ):
            async with scope() as session:
                assert (await session.exec(text("SELECT count(*) FROM authz_role"))).scalar_one() >= 3
        await memory_service.run_migrations()
    finally:
        await memory_service.teardown()


@pytest.mark.parametrize("memory_service", ["sqlite:///:memory:"], indirect=True)
async def test_unknown_memory_revision_is_refused_before_tables_change(memory_service, monkeypatch):
    monkeypatch.setattr("langflow.services.deps.get_db_service", lambda: memory_service)
    try:
        async with memory_service.engine.begin() as connection:
            await connection.exec_driver_sql("CREATE TABLE alembic_version (version_num VARCHAR(32) PRIMARY KEY)")
            await connection.exec_driver_sql("INSERT INTO alembic_version VALUES ('unknown_future_revision')")
            await connection.exec_driver_sql("CREATE TABLE customer_data (value TEXT)")
            await connection.exec_driver_sql("INSERT INTO customer_data VALUES ('preserve me')")
        for operation in (initialize_database, memory_service.run_migrations):
            with pytest.raises(DatabaseRevisionError, match="unknown_future_revision"):
                await operation()
        async with memory_service.engine.connect() as connection:
            assert await connection.run_sync(lambda sync: set(inspect(sync).get_table_names())) == {
                "alembic_version",
                "customer_data",
            }
            assert (await connection.execute(text("SELECT value FROM customer_data"))).scalar_one() == "preserve me"
    finally:
        await memory_service.teardown()


@pytest.mark.parametrize("memory_service", ["sqlite:///:memory:"], indirect=True)
async def test_memory_contents_survive_connection_checkout_with_recycling_configured(memory_service):
    memory_service.settings_service.settings.db_connection_settings["pool_recycle"] = 0
    await memory_service.engine.dispose()
    memory_service.reload_engine()
    try:
        async with memory_service.engine.begin() as connection:
            await connection.exec_driver_sql("CREATE TABLE memory_content (value TEXT)")
            await connection.exec_driver_sql("INSERT INTO memory_content VALUES ('keep me')")
        async with memory_service.engine.connect() as connection:
            assert (await connection.execute(text("SELECT value FROM memory_content"))).scalar_one() == "keep me"
    finally:
        await memory_service.teardown()

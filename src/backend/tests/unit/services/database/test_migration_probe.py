from unittest.mock import AsyncMock, MagicMock

import pytest
import sqlalchemy as sa
from langflow.services.database import migration
from langflow.services.database.migration import get_current_alembic_heads
from langflow.services.database.session import NoopSession
from lfx.services.session import NoopSession as LfxNoopSession
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


async def test_sqlite_migration_probe_handles_missing_table_and_multiple_heads(tmp_path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'migration-probe.db'}")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            assert await get_current_alembic_heads(session) == ()
            await session.connection()
            await session.execute(
                sa.text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)")
            )
            await session.execute(sa.text("INSERT INTO alembic_version (version_num) VALUES ('head_a'), ('head_b')"))
            assert set(await get_current_alembic_heads(session)) == {"head_a", "head_b"}
    finally:
        await engine.dispose()


async def test_postgresql_probe_contract_uses_migration_context(monkeypatch) -> None:
    sync_connection = MagicMock()
    sync_connection.dialect.name = "postgresql"
    context = MagicMock()
    context.get_current_heads.return_value = ("postgres_head",)
    configure = MagicMock(return_value=context)
    monkeypatch.setattr(migration.MigrationContext, "configure", configure)
    async_connection = MagicMock()

    async def run_sync(callback):
        return callback(sync_connection)

    async_connection.run_sync = run_sync
    session = MagicMock()
    session.connection = AsyncMock(return_value=async_connection)

    assert await get_current_alembic_heads(session) == ("postgres_head",)
    configure.assert_called_once_with(sync_connection)


@pytest.mark.parametrize("session_type", [NoopSession, LfxNoopSession])
async def test_noop_session_reports_no_migration_heads(session_type) -> None:
    assert await get_current_alembic_heads(session_type()) == ()


async def test_migration_probe_propagates_connection_failure() -> None:
    session = MagicMock()
    session.connection = AsyncMock(side_effect=ConnectionError("database unavailable"))

    with pytest.raises(ConnectionError, match="database unavailable"):
        await get_current_alembic_heads(session)

"""Tests for collaborative editing database foundation: flow.latest_operation_revision."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.user.model import User
from langflow.utils import migration
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

_TEST_PASSWORD = "hashed"  # noqa: S105  # pragma: allowlist secret
_ALEMBIC_SCRIPT_LOCATION = Path(__file__).resolve().parents[7] / "src/backend/base/langflow/alembic"


@pytest.fixture(name="flow_revision_db_engine")
def flow_revision_db_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):  # noqa: ARG001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


@pytest.fixture(name="flow_revision_session")
async def flow_revision_session(flow_revision_db_engine):
    async with flow_revision_db_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    async with AsyncSession(flow_revision_db_engine, expire_on_commit=False) as session:
        yield session
    async with flow_revision_db_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await flow_revision_db_engine.dispose()


async def _create_user(session: AsyncSession, username: str | None = None) -> User:
    user = User(username=username or f"user_{uuid4().hex[:8]}", password=_TEST_PASSWORD)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def _create_flow(session: AsyncSession, user_id) -> Flow:
    flow = Flow(
        name=f"flow_{uuid4().hex[:8]}",
        user_id=user_id,
        data={"nodes": [], "edges": []},
    )
    session.add(flow)
    await session.commit()
    await session.refresh(flow)
    return flow


@pytest.mark.asyncio
class TestFlowLatestOperationRevision:
    async def test_flow_latest_operation_revision_defaults_to_zero(self, flow_revision_session):
        user = await _create_user(flow_revision_session)
        flow = await _create_flow(flow_revision_session, user.id)
        assert flow.latest_operation_revision == 0

    async def test_flow_latest_operation_revision_can_be_updated(self, flow_revision_session):
        user = await _create_user(flow_revision_session)
        flow = await _create_flow(flow_revision_session, user.id)

        flow.latest_operation_revision = 3
        flow_revision_session.add(flow)
        await flow_revision_session.commit()
        await flow_revision_session.refresh(flow)

        assert flow.latest_operation_revision == 3


def test_migration_adds_latest_operation_revision(tmp_path):
    """Alembic migration creates flow.latest_operation_revision."""
    db_path = tmp_path / "collab_migration.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"

    alembic_cfg = Config()
    alembic_cfg.set_main_option("script_location", str(_ALEMBIC_SCRIPT_LOCATION))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    command.upgrade(alembic_cfg, "e8f1a2b3c4d5")  # pragma: allowlist secret

    from sqlalchemy import create_engine

    engine = create_engine(f"sqlite:///{db_path}")
    conn = engine.connect()
    try:
        assert migration.column_exists("flow", "latest_operation_revision", conn)
    finally:
        conn.close()
        engine.dispose()

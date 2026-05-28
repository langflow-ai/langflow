"""Tests for collaborative editing database foundation: flow.latest_operation_revision and flow_operation."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_operation.crud import (
    create_flow_operation,
    get_flow_operation_by_revision,
    list_flow_operations_after_revision,
)
from langflow.services.database.models.flow_operation.model import FlowOperation, FlowOperationActorDelegate
from langflow.services.database.models.user.model import User
from langflow.utils import migration
from sqlalchemy import event, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

_TEST_PASSWORD = "hashed"  # noqa: S105  # pragma: allowlist secret
_ALEMBIC_SCRIPT_LOCATION = Path(__file__).resolve().parents[7] / "src/backend/base/langflow/alembic"


@pytest.fixture(name="flow_ops_db_engine")
def flow_ops_db_engine():
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


@pytest.fixture(name="flow_ops_session")
async def flow_ops_session(flow_ops_db_engine):
    async with flow_ops_db_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    async with AsyncSession(flow_ops_db_engine, expire_on_commit=False) as session:
        yield session
    async with flow_ops_db_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await flow_ops_db_engine.dispose()


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
    async def test_flow_latest_operation_revision_defaults_to_zero(self, flow_ops_session):
        user = await _create_user(flow_ops_session)
        flow = await _create_flow(flow_ops_session, user.id)
        assert flow.latest_operation_revision == 0


@pytest.mark.asyncio
class TestFlowOperationModel:
    async def test_create_and_read_flow_operation(self, flow_ops_session):
        user = await _create_user(flow_ops_session)
        flow = await _create_flow(flow_ops_session, user.id)

        entry = await create_flow_operation(
            flow_ops_session,
            flow_id=flow.id,
            protocol_version=1,
            revision=1,
            client_id="tab-abc",
            actor_user_id=user.id,
            actor_delegate=FlowOperationActorDelegate.SELF,
            forward_ops=[{"type": "update_nodes", "nodes": []}],
            backward_ops=[{"type": "update_nodes", "nodes": [{"id": "node-1", "position": {"x": 0, "y": 0}}]}],
        )
        await flow_ops_session.commit()
        await flow_ops_session.refresh(entry)

        assert entry.id is not None
        assert entry.flow_id == flow.id
        assert entry.revision == 1
        assert entry.protocol_version == 1
        assert entry.client_id == "tab-abc"
        assert entry.actor_user_id == user.id
        assert entry.actor_delegate == FlowOperationActorDelegate.SELF
        assert entry.forward_ops == [{"type": "update_nodes", "nodes": []}]
        assert entry.backward_ops == [
            {"type": "update_nodes", "nodes": [{"id": "node-1", "position": {"x": 0, "y": 0}}]}
        ]
        assert entry.created_at is not None

    async def test_unique_flow_id_revision_constraint(self, flow_ops_session):
        user = await _create_user(flow_ops_session)
        flow = await _create_flow(flow_ops_session, user.id)

        await create_flow_operation(
            flow_ops_session,
            flow_id=flow.id,
            protocol_version=1,
            revision=1,
            client_id="tab-1",
            actor_user_id=user.id,
            actor_delegate=FlowOperationActorDelegate.SELF,
            forward_ops=[],
            backward_ops=[],
        )
        await flow_ops_session.commit()

        with pytest.raises(IntegrityError, match=r"UNIQUE constraint failed|unique constraint"):
            await create_flow_operation(
                flow_ops_session,
                flow_id=flow.id,
                protocol_version=1,
                revision=1,
                client_id="tab-2",
                actor_user_id=user.id,
                actor_delegate=FlowOperationActorDelegate.SELF,
                forward_ops=[],
                backward_ops=[],
            )

    async def test_cascade_delete_when_flow_deleted(self, flow_ops_session):
        user = await _create_user(flow_ops_session)
        flow = await _create_flow(flow_ops_session, user.id)

        entry = await create_flow_operation(
            flow_ops_session,
            flow_id=flow.id,
            protocol_version=1,
            revision=1,
            client_id="tab-cascade",
            actor_user_id=user.id,
            actor_delegate=FlowOperationActorDelegate.AGENT,
            forward_ops=[],
            backward_ops=[],
        )
        await flow_ops_session.commit()
        await flow_ops_session.refresh(entry)
        operation_id = entry.id

        await flow_ops_session.delete(flow)
        await flow_ops_session.commit()

        result = await flow_ops_session.exec(select(FlowOperation).where(FlowOperation.id == operation_id))
        assert result.first() is None


@pytest.mark.asyncio
class TestFlowOperationCrud:
    async def test_list_operations_after_revision_ordered(self, flow_ops_session):
        user = await _create_user(flow_ops_session)
        flow = await _create_flow(flow_ops_session, user.id)

        for revision in (1, 2, 3):
            await create_flow_operation(
                flow_ops_session,
                flow_id=flow.id,
                protocol_version=1,
                revision=revision,
                client_id=f"tab-{revision}",
                actor_user_id=user.id,
                actor_delegate=FlowOperationActorDelegate.SELF,
                forward_ops=[],
                backward_ops=[],
            )
        await flow_ops_session.commit()

        rows = await list_flow_operations_after_revision(flow_ops_session, flow.id, after_revision=1, page_size=100)
        assert [row.revision for row in rows] == [2, 3]

        by_revision = await get_flow_operation_by_revision(flow_ops_session, flow.id, 2)
        assert by_revision is not None
        assert by_revision.client_id == "tab-2"


def test_migration_adds_revision_and_flow_operation(tmp_path):
    """Alembic migration creates flow.latest_operation_revision and the flow_operation table."""
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
        assert migration.table_exists("flow_operation", conn)
        assert migration.constraint_exists("flow_operation", "unique_flow_operation_revision", conn)

        inspector = inspect(conn)
        flow_operation_columns = {column["name"] for column in inspector.get_columns("flow_operation")}
        assert {"forward_ops", "backward_ops", "actor_delegate"}.issubset(flow_operation_columns)
        flow_operation_indexes = {idx["name"] for idx in inspector.get_indexes("flow_operation")}
        assert "ix_flow_operation_flow_id_created_at" in flow_operation_indexes
    finally:
        conn.close()
        engine.dispose()

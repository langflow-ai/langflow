"""History reads take no lock, and compaction takes only the flow's advisory lock (PostgreSQL).

- A history read (timeline, graph at a revision) completes while a writer holds
  the flow's advisory lock and its row lock.
- Compaction completes while another transaction holds ``FOR SHARE`` on the flow
  row (what history reads used to take): it no longer takes the row lock.
- A read that races compaction (its checkpoint's rows deleted under it) retries
  and returns the right graph.

Runs on PostgreSQL only (``LANGFLOW_TEST_DATABASE_URI``).
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from langflow.services.database.models.flow.guards import lock_flow_for_update
from langflow.services.database.models.flow.model import Flow, FlowGraphWriteOptions
from langflow.services.database.models.user.model import User
from langflow.services.database.service import SQLModel
from langflow.services.deps import get_settings_service
from langflow.services.flow_history import replay as replay_module
from langflow.services.flow_history.errors import FlowHistoryCorruptionError
from langflow.services.flow_history.maintenance import checkpoint_if_due, compact_if_due
from langflow.services.flow_history.recorder import write_flow_graph
from langflow.services.flow_history.replay import reconstruct_graph
from langflow.services.flow_history.timeline import read_timeline
from langflow.services.flow_multiplayer.oplog import lock_key
from lfx.services.flow_operations import graphs_equal
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from tests.unit.alembic.test_migration_execution import db_url  # noqa: F401

READ_TIMEOUT = 5


def _graph(value: str) -> dict:
    node = {"id": "a", "data": {"node": {"display_name": "a", "template": {"t": {"value": value}}}}}
    return {"nodes": [node], "edges": []}


@pytest.fixture
async def engine(db_url):  # noqa: F811
    if not db_url.startswith("postgresql"):
        pytest.skip("advisory locks and row locks are PostgreSQL behaviour")
    engine = create_async_engine(db_url)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
async def flow_id(engine):
    async with AsyncSession(engine, expire_on_commit=False) as session:
        user = User(username=f"reads-{uuid4().hex[:8]}", password="hashed-test-value")  # noqa: S106
        session.add(user)
        await session.flush()
        flow = Flow.model_validate({"name": "reads", "user_id": user.id, "data": _graph("start")})
        session.add(flow)
        await session.commit()
        return flow.id, user.id


async def _write(engine, flow_id, actor_id, value: str) -> None:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        flow = await session.get(Flow, flow_id)
        await lock_flow_for_update(session, flow)
        await write_flow_graph(session, flow, _graph(value), actor_id=actor_id, options=FlowGraphWriteOptions())
        session.add(flow)
        await session.commit()


async def _maintain(engine, flow_id) -> None:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        flow = await session.get(Flow, flow_id)
        await lock_flow_for_update(session, flow)
        await checkpoint_if_due(session, flow)
        await compact_if_due(session, flow)
        await session.commit()


@pytest.fixture
def small_history(monkeypatch):
    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "flow_history_enabled", True)
    monkeypatch.setattr(settings, "flow_revision_checkpoint_cadence", 2)
    monkeypatch.setattr(settings, "flow_revision_retention_window", 3)


async def test_history_reads_do_not_wait_for_a_writer(engine, flow_id, small_history):  # noqa: ARG001
    flow_uuid, actor_id = flow_id
    for value in ("one", "two", "three"):
        await _write(engine, flow_uuid, actor_id, value)
    async with engine.connect() as writer:
        # A writer in the middle of its transaction: the advisory lock and the row lock.
        await writer.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"), {"k": lock_key(flow_uuid)})
        await writer.execute(text("SELECT id FROM flow WHERE id = :id FOR UPDATE"), {"id": flow_uuid})
        async with AsyncSession(engine) as session:
            flow = await session.get(Flow, flow_uuid)
            graph = await asyncio.wait_for(
                reconstruct_graph(session, flow_uuid, 2, latest_revision=3), timeout=READ_TIMEOUT
            )
            page = await asyncio.wait_for(
                read_timeline(
                    session, flow, before=None, limit=10, include_operations=True, known_variable_names=frozenset()
                ),
                timeout=READ_TIMEOUT,
            )
        await writer.rollback()
    assert graphs_equal(graph, _graph("two"))
    assert [entry.end_revision for entry in page.entries] == [3, 2, 1]
    assert page.earliest_revision == 1


async def _first_retained(engine, flow_id) -> int:
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT min(start_revision) FROM flow_operation WHERE flow_id = :id"), {"id": flow_id}
        )
        return result.scalar_one()


async def test_compaction_does_not_wait_for_a_row_share_lock(engine, flow_id, small_history):  # noqa: ARG001
    flow_uuid, actor_id = flow_id
    for value in range(1, 7):
        await _write(engine, flow_uuid, actor_id, str(value))
        await _maintain(engine, flow_uuid)
    for value in (7, 8):
        await _write(engine, flow_uuid, actor_id, str(value))
    before = await _first_retained(engine, flow_uuid)
    async with engine.connect() as reader:
        await reader.execute(text("SELECT id FROM flow WHERE id = :id FOR SHARE"), {"id": flow_uuid})
        await asyncio.wait_for(_maintain(engine, flow_uuid), timeout=READ_TIMEOUT)
        await reader.rollback()
    assert await _first_retained(engine, flow_uuid) > before  # it did compact
    async with AsyncSession(engine) as session:
        assert graphs_equal(await reconstruct_graph(session, flow_uuid, 8, latest_revision=8), _graph("8"))


async def test_a_read_that_races_compaction_retries(engine, flow_id, small_history, monkeypatch):  # noqa: ARG001
    flow_uuid, actor_id = flow_id
    for value in ("one", "two", "three"):
        await _write(engine, flow_uuid, actor_id, value)
    real = replay_module._reconstruct
    calls = []

    async def racing(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            # As if compaction deleted the rows after the checkpoint this read picked.
            raise FlowHistoryCorruptionError(flow_uuid, "missing revisions", revision=1)
        return await real(*args, **kwargs)

    monkeypatch.setattr(replay_module, "_reconstruct", racing)
    async with AsyncSession(engine) as session:
        graph = await reconstruct_graph(session, flow_uuid, 3, latest_revision=3)
    assert len(calls) == 2
    assert graphs_equal(graph, _graph("three"))

"""The recorder on each supported database, driven directly rather than through the API.

The API tests run on SQLite only. These run the same seam on PostgreSQL too
(when ``LANGFLOW_TEST_DATABASE_URI`` is set), where retry lookup uses jsonb
containment over a GIN index and the flow lock is a real row lock.
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from langflow.services.database.models.flow.guards import lock_flow_for_update
from langflow.services.database.models.flow.model import Flow, FlowGraphWriteOptions
from langflow.services.database.models.flow_operation import FlowOperation
from langflow.services.database.models.user.model import User
from langflow.services.database.service import SQLModel
from langflow.services.flow_history.recorder import write_flow_graph
from langflow.services.flow_history.replay import reconstruct_graph
from lfx.services.flow_operations import graphs_equal
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from tests.unit.alembic.test_migration_execution import db_url  # noqa: F401


def _node(node_id: str, value: str) -> dict:
    return {"id": node_id, "data": {"node": {"display_name": node_id, "template": {"t": {"value": value}}}}}


def _graph(value: str) -> dict:
    return {"nodes": [_node("a", value)], "edges": []}


@pytest.fixture
async def engine(db_url):  # noqa: F811
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
        user = User(username=f"recorder-{uuid4().hex[:8]}", password="hashed-test-value")  # noqa: S106
        session.add(user)
        await session.flush()
        flow = Flow.model_validate({"name": "recorded", "user_id": user.id, "data": _graph("start")})
        session.add(flow)
        await session.commit()
        return flow.id, user.id


async def _write(engine, flow_id, actor_id, target: dict, **options):
    async with AsyncSession(engine, expire_on_commit=False) as session:
        flow = await session.get(Flow, flow_id)
        await lock_flow_for_update(session, flow)
        result = await write_flow_graph(
            session, flow, target, actor_id=actor_id, options=FlowGraphWriteOptions(**options)
        )
        session.add(flow)
        await session.commit()
        return result


async def test_retry_lookup_finds_the_original_request(engine, flow_id):
    flow_uuid, actor_id = flow_id
    request_id = uuid4()

    first = await _write(engine, flow_uuid, actor_id, _graph("one"), request_id=request_id)
    await _write(engine, flow_uuid, actor_id, _graph("two"))
    retry = await _write(engine, flow_uuid, actor_id, _graph("one"), request_id=request_id)

    assert retry.deduplicated is True
    assert (retry.start_revision, retry.end_revision) == (first.start_revision, first.end_revision)
    assert retry.latest_revision == 2


async def test_replay_matches_every_write(engine, flow_id):
    flow_uuid, actor_id = flow_id
    values = ["one", "two", "three"]
    for value in values:
        await _write(engine, flow_uuid, actor_id, _graph(value))

    async with AsyncSession(engine) as session:
        flow = await session.get(Flow, flow_uuid)
        for revision, value in enumerate(["start", *values]):
            graph = await reconstruct_graph(session, flow_uuid, revision, latest_revision=flow.latest_revision)
            assert graphs_equal(graph, _graph(value))


async def test_concurrent_writers_extend_one_head(engine, flow_id):
    flow_uuid, actor_id = flow_id

    async def write(value: str):
        # SQLite admits one writer at a time and reports the rest as busy; the
        # API retries those, and so does this test.
        for _ in range(20):
            try:
                return await _write(engine, flow_uuid, actor_id, _graph(value))
            except Exception as exc:
                if "locked" not in str(exc).lower():
                    raise
                await asyncio.sleep(0.05)
        pytest.fail("writer never acquired the lock")

    await asyncio.gather(*(write(f"writer {index}") for index in range(5)))

    async with AsyncSession(engine) as session:
        rows = (
            await session.exec(
                select(FlowOperation)
                .where(FlowOperation.flow_id == flow_uuid)
                .order_by(col(FlowOperation.start_revision))
            )
        ).all()
        flow = await session.get(Flow, flow_uuid)
    assert [row.start_revision for row in rows] == list(range(1, len(rows) + 1))
    assert flow.latest_revision == flow.current_revision == len(rows) == 5

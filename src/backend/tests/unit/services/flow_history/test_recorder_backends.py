"""The recorder on each supported database, driven directly rather than through the API.

The API tests run on SQLite only. These run the same seam on PostgreSQL too
(when ``LANGFLOW_TEST_DATABASE_URI`` is set), where retry lookup uses jsonb
containment over a GIN index and the flow lock is a real row lock.
"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import threading
from uuid import uuid4

import pytest
from langflow.services.database.models.flow.guards import lock_flow_for_update
from langflow.services.database.models.flow.model import Flow, FlowGraphWriteOptions
from langflow.services.database.models.flow_operation import FlowOperation
from langflow.services.database.models.flow_version.crud import create_flow_version_entry
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.database.models.user.model import User
from langflow.services.database.service import SQLModel
from langflow.services.deps import get_settings_service
from langflow.services.flow_history import recorder
from langflow.services.flow_history.errors import FlowHistoryCorruptionError, FlowRevisionNotRetainedError
from langflow.services.flow_history.maintenance import checkpoint_if_due, compact_if_due
from langflow.services.flow_history.recorder import _JsonText, checkpoint_fields, projection_matches, write_flow_graph
from langflow.services.flow_history.replay import reconstruct_graph, retention_cutoff, verify_checkpoint
from lfx.services.flow_operations import graphs_equal
from sqlalchemy import Text, bindparam, cast, update
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


async def test_compaction_deletes_old_rows_through_the_append_only_trigger(engine, flow_id, monkeypatch):
    # On PostgreSQL the trigger refuses deletes of a live flow's rows unless the
    # transaction is marked as maintenance; this is the path that marks it.
    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "flow_revision_checkpoint_cadence", 2)
    monkeypatch.setattr(settings, "flow_revision_retention_window", 3)
    flow_uuid, actor_id = flow_id
    for value in range(1, 9):
        await _write(engine, flow_uuid, actor_id, _graph(str(value)))
        async with AsyncSession(engine, expire_on_commit=False) as session:
            flow = await session.get(Flow, flow_uuid)
            await lock_flow_for_update(session, flow)
            await checkpoint_if_due(session, flow)
            await compact_if_due(session, flow)
            await session.commit()

    async with AsyncSession(engine) as session:
        flow = await session.get(Flow, flow_uuid)
        starts = (
            await session.exec(select(FlowOperation.start_revision).where(FlowOperation.flow_id == flow_uuid))
        ).all()
        assert min(starts) > 1
        cutoff = await retention_cutoff(session, flow_uuid, flow.latest_revision)
        for revision in range(cutoff, 9):
            graph = await reconstruct_graph(session, flow_uuid, revision, latest_revision=flow.latest_revision)
            assert graphs_equal(graph, _graph(str(revision)))
        with pytest.raises(FlowRevisionNotRetainedError):
            await reconstruct_graph(session, flow_uuid, cutoff - 1, latest_revision=flow.latest_revision)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


async def _stored_text(session: AsyncSession, column, row_id) -> str:
    """The JSON text a row holds, as the database stores it."""
    model = column.class_
    return (await session.exec(select(cast(column, Text)).where(model.id == row_id))).one()


async def _set_stored_text(session: AsyncSession, column, row_id, text: str) -> None:
    """Store ``text`` in a JSON column as it is (no serialization), as the checkpoint writers do."""
    model = column.class_
    await session.exec(
        update(model).where(model.id == row_id).values({column.key: bindparam(None, text, type_=_JsonText())})
    )


async def _checkpoint_at_head(engine, flow_uuid, actor_id, monkeypatch) -> None:
    """Write until the legacy maintenance checkpoints the flow at its current revision."""
    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "flow_revision_checkpoint_cadence", 2)
    for value in ("one", "two"):
        await _write(engine, flow_uuid, actor_id, _graph(value))
    async with AsyncSession(engine, expire_on_commit=False) as session:
        flow = await session.get(Flow, flow_uuid)
        await lock_flow_for_update(session, flow)
        assert await checkpoint_if_due(session, flow) is not None
        await session.commit()


async def test_checkpoint_rows_store_the_text_they_hash(engine, flow_id, monkeypatch):
    """Every checkpoint row's hash is the SHA-256 of the exact JSON text the row stores."""
    flow_uuid, actor_id = flow_id
    await _checkpoint_at_head(engine, flow_uuid, actor_id, monkeypatch)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        # A saved version made a checkpoint (v1 snapshot): the caller stores a copy of the dict.
        flow = await session.get(Flow, flow_uuid)
        fields = await checkpoint_fields(session, flow)
        assert fields["operation_revision"] == 2
        await create_flow_version_entry(session, flow_uuid, actor_id, data=copy.deepcopy(flow.data), **fields)
        await session.commit()
    async with AsyncSession(engine) as session:
        rows = (
            await session.exec(
                select(
                    FlowVersion.id, FlowVersion.operation_revision, FlowVersion.version_number, FlowVersion.graph_hash
                )
                .where(FlowVersion.flow_id == flow_uuid, col(FlowVersion.graph_hash).is_not(None))
                .order_by(col(FlowVersion.operation_revision), col(FlowVersion.created_at))
            )
        ).all()
        # Revision 0 (start of history), the maintenance checkpoint at 2, the saved version at 2.
        assert [(revision, number is None) for _id, revision, number, _hash in rows] == [
            (0, True),
            (2, True),
            (2, False),
        ]
        for row_id, _revision, _number, graph_hash in rows:
            assert _sha256(await _stored_text(session, FlowVersion.data, row_id)) == graph_hash
        # The maintenance checkpoint stores Flow.data's text as it is.
        flow_text = await _stored_text(session, Flow.data, flow_uuid)
        assert await _stored_text(session, FlowVersion.data, rows[1][0]) == flow_text
        assert json.loads(flow_text) == _graph("two")


async def test_projection_matches_at_a_checkpoint(engine, flow_id, monkeypatch):
    """At a checkpoint's revision: byte-identical text matches without the engine; other text falls back to it."""
    flow_uuid, actor_id = flow_id
    await _checkpoint_at_head(engine, flow_uuid, actor_id, monkeypatch)
    real_engine = recorder._engine

    async def no_engine(name, *_args, **_kwargs):
        pytest.fail(f"engine call {name} on byte-identical text")

    async with AsyncSession(engine, expire_on_commit=False) as session:
        flow = await session.get(Flow, flow_uuid)
        monkeypatch.setattr(recorder, "_engine", no_engine)
        assert await projection_matches(session, flow)
        monkeypatch.setattr(recorder, "_engine", real_engine)
        # The same graph as other bytes: the hash differs, the engine finds the same graph.
        await _set_stored_text(session, Flow.data, flow_uuid, json.dumps(_graph("two"), separators=(",", ":")))
        await session.commit()
        await session.refresh(flow)
        assert await projection_matches(session, flow)
        # Another graph at the same revision.
        await _set_stored_text(session, Flow.data, flow_uuid, json.dumps(_graph("edited")))
        await session.commit()
        await session.refresh(flow)
        assert not await projection_matches(session, flow)


async def test_verify_checkpoint_detects_a_changed_byte(engine, flow_id, monkeypatch):
    """A checkpoint whose stored text changed by one byte fails verification, even as the same graph."""
    flow_uuid, actor_id = flow_id
    await _checkpoint_at_head(engine, flow_uuid, actor_id, monkeypatch)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        checkpoint = (
            await session.exec(
                select(FlowVersion).where(FlowVersion.flow_id == flow_uuid, FlowVersion.operation_revision == 2)
            )
        ).one()
        await verify_checkpoint(session, checkpoint)
        text = await _stored_text(session, FlowVersion.data, checkpoint.id)
        await _set_stored_text(session, FlowVersion.data, checkpoint.id, text + " ")
        with pytest.raises(FlowHistoryCorruptionError):
            await verify_checkpoint(session, checkpoint)


# Whole-flow engine calls of a legacy save; each must run in a worker thread, never on the event loop.
WHOLE_FLOW_CALLS = frozenset({"validate", "repair", "ops_diff", "graph_hash", "graphs_equal", "apply", "GraphState"})


class _ThreadSpy:
    """The engine object, recording for each whole-flow call whether it ran on the event loop's thread."""

    def __init__(self, real, loop_thread: int, calls: list[tuple[str, bool]]) -> None:
        self._real = real
        self._loop_thread = loop_thread
        self._calls = calls

    def __getattr__(self, name: str):
        value = getattr(self._real, name)
        if name not in WHOLE_FLOW_CALLS:
            return value

        def spy(*args, **kwargs):
            self._calls.append((name, threading.get_ident() == self._loop_thread))
            return value(*args, **kwargs)

        return spy


@pytest.mark.parametrize("mode", ["nocache", "cache", "wal"])
async def test_legacy_save_runs_whole_flow_engine_calls_off_the_event_loop(engine, flow_id, mode, monkeypatch):
    """A legacy save (start of history, a later save, a stale token with an unchanged graph) never blocks the loop.

    The multiplayer path runs large engine calls in a worker thread; the legacy path must too,
    or one 14 MB save stalls every other request of the process for seconds.
    """
    if mode != "nocache" and engine.dialect.name != "postgresql":
        pytest.skip("modes cache and wal need PostgreSQL")
    from langflow.services.flow_multiplayer import checkpoint, config
    from langflow.services.flow_multiplayer.cache import CACHE

    calls: list[tuple[str, bool]] = []
    spy = _ThreadSpy(config.engine(), threading.get_ident(), calls)
    monkeypatch.setattr(config, "engine", lambda: spy)
    monkeypatch.setattr(config, "write_mode", lambda: mode)
    # The checkpoint task runs after the commit, outside this test's database.
    monkeypatch.setattr(checkpoint, "after_write", lambda *_args: None)
    CACHE.clear()
    flow_uuid, actor_id = flow_id
    try:
        await _write(engine, flow_uuid, actor_id, _graph("one"))
        await _write(engine, flow_uuid, actor_id, _graph("two"))
        async with AsyncSession(engine, expire_on_commit=False) as session:
            flow = await session.get(Flow, flow_uuid)
            await lock_flow_for_update(session, flow)
            await write_flow_graph(session, flow, _graph("two"), actor_id=actor_id, expected_version_token=uuid4())
            await session.commit()
    finally:
        CACHE.clear()

    names = {name for name, _on_loop in calls}
    assert {"validate", "ops_diff", "graphs_equal"} <= names, calls
    # A checkpoint's hash is SHA-256 of its text, not an engine call.
    assert "graph_hash" not in names, calls
    assert [name for name, on_loop in calls if on_loop] == []

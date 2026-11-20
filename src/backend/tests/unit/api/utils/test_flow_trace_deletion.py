"""Regression tests for deleting traces attached to a flow."""

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from langflow.api.utils import flow_utils
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.traces.model import SpanTable, TraceTable
from langflow.services.evaluations import cleanup as evaluation_cleanup
from langflow.services.memory_base import flow_cleanup
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.selectable import Select
from sqlmodel import select


def _mock_cascade_delete_dependencies(monkeypatch):
    """Stub cleanup services unrelated to persisted flow and trace rows.

    @param monkeypatch: Pytest fixture used to isolate external cleanup work.
    @returns: None.
    """
    monkeypatch.setattr(flow_utils, "check_flow_has_deployed_versions", AsyncMock())
    monkeypatch.setattr(flow_cleanup, "purge_flow_memory_bases", AsyncMock(return_value=[]))
    monkeypatch.setattr(flow_utils, "delete_triggers", AsyncMock())
    monkeypatch.setattr(evaluation_cleanup, "detach_flow", AsyncMock())


async def _seed_flow_trace_rows(session: AsyncSession) -> tuple[UUID, UUID, UUID, UUID, UUID, UUID]:
    """Insert target and unrelated flows, each with one trace and span.

    @param session: SQLite test session used to seed the rows.
    @returns: Target and unrelated flow, trace, and span IDs in that order.
    """
    target_flow_id, unrelated_flow_id = uuid4(), uuid4()
    target_trace_id, unrelated_trace_id = uuid4(), uuid4()
    target_span_id, unrelated_span_id = uuid4(), uuid4()
    session.add_all(
        [
            Flow(id=target_flow_id, name="target"),
            Flow(id=unrelated_flow_id, name="unrelated"),
            TraceTable(id=target_trace_id, flow_id=target_flow_id, name="target trace"),
            TraceTable(id=unrelated_trace_id, flow_id=unrelated_flow_id, name="unrelated trace"),
            SpanTable(id=target_span_id, trace_id=target_trace_id, name="target span"),
            SpanTable(id=unrelated_span_id, trace_id=unrelated_trace_id, name="unrelated span"),
        ]
    )
    await session.commit()
    return (
        target_flow_id,
        unrelated_flow_id,
        target_trace_id,
        unrelated_trace_id,
        target_span_id,
        unrelated_span_id,
    )


async def test_cascade_delete_flow_keeps_large_trace_deletes_below_postgres_bind_limit(monkeypatch):
    """Ensure trace cleanup uses bounded SQL parameters for large histories.

    @param monkeypatch: pytest fixture used to isolate the database side effects.
    @returns: None; asserts that no trace IDs are materialized and both deletes remain bounded.
    """
    flow_id = uuid4()
    materialized_trace_queries = 0
    trace_delete_parameter_counts = []
    trace_delete_sync_options = []

    async def record_exec(statement):
        """Record generated SQL and supply the large trace result for the regression.

        @param statement: SQLAlchemy statement issued by flow deletion.
        @returns: A result object sufficient for cascade_delete_flow.
        """
        nonlocal materialized_trace_queries

        if isinstance(statement, Select):
            table_names = {table.name for table in statement.get_final_froms()}
            if TraceTable.__tablename__ in table_names:
                materialized_trace_queries += 1
                return SimpleNamespace(all=lambda: list(range(65_536)))
            return SimpleNamespace(all=list)

        table = getattr(statement, "table", None)
        if table is not None and table.name in {SpanTable.__tablename__, TraceTable.__tablename__}:
            compiled = statement.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"render_postcompile": True},
            )
            trace_delete_parameter_counts.append(len(compiled.params))
            trace_delete_sync_options.append(statement.get_execution_options().get("synchronize_session"))
        return SimpleNamespace(rowcount=1)

    monkeypatch.setattr(flow_utils, "check_flow_has_deployed_versions", AsyncMock())
    monkeypatch.setattr(flow_cleanup, "purge_flow_memory_bases", AsyncMock(return_value=[]))
    monkeypatch.setattr(flow_utils, "delete_triggers", AsyncMock())
    monkeypatch.setattr(evaluation_cleanup, "detach_flow", AsyncMock())
    session = SimpleNamespace(exec=AsyncMock(side_effect=record_exec))

    assert await flow_utils.cascade_delete_flow(session, flow_id)
    assert materialized_trace_queries == 0
    assert trace_delete_parameter_counts == [1, 1]
    assert trace_delete_sync_options == [False, False]


async def test_cascade_delete_flow_preserves_unrelated_trace_rows(async_session, monkeypatch):
    """Delete only the target flow's trace and span rows in SQLite.

    @param async_session: SQLite-backed async session fixture.
    @param monkeypatch: Pytest fixture used to isolate external cleanup work.
    @returns: None; asserts the exact flow, trace, and span rows remaining.
    """
    _mock_cascade_delete_dependencies(monkeypatch)
    (
        target_flow_id,
        unrelated_flow_id,
        _target_trace_id,
        unrelated_trace_id,
        _target_span_id,
        unrelated_span_id,
    ) = await _seed_flow_trace_rows(async_session)

    assert await flow_utils.cascade_delete_flow(async_session, target_flow_id)
    await async_session.commit()

    remaining_flow_ids = (await async_session.exec(select(Flow.id))).all()
    remaining_trace_ids = (await async_session.exec(select(TraceTable.id))).all()
    remaining_span_ids = (await async_session.exec(select(SpanTable.id))).all()
    assert set(remaining_flow_ids) == {unrelated_flow_id}
    assert set(remaining_trace_ids) == {unrelated_trace_id}
    assert set(remaining_span_ids) == {unrelated_span_id}


async def test_cascade_delete_flow_rolls_back_when_trace_delete_fails(async_session, monkeypatch):
    """Verify a failed trace delete can roll back earlier flow cleanup deletes.

    @param async_session: SQLite-backed async session fixture.
    @param monkeypatch: Pytest fixture used to inject a trace-delete failure.
    @returns: None; asserts all seeded rows remain after rollback.
    """
    _mock_cascade_delete_dependencies(monkeypatch)
    (
        target_flow_id,
        unrelated_flow_id,
        target_trace_id,
        unrelated_trace_id,
        target_span_id,
        unrelated_span_id,
    ) = await _seed_flow_trace_rows(async_session)
    original_exec = async_session.exec

    async def fail_trace_delete(statement):
        """Raise before executing the target trace delete.

        @param statement: SQLAlchemy statement issued by flow deletion.
        @returns: The original execution result for non-trace statements.
        """
        table = getattr(statement, "table", None)
        if table is not None and table.name == TraceTable.__tablename__:
            raise RuntimeError
        return await original_exec(statement)

    monkeypatch.setattr(async_session, "exec", fail_trace_delete)
    with pytest.raises(RuntimeError, match="Unable to cascade delete flow"):
        await flow_utils.cascade_delete_flow(async_session, target_flow_id)

    await async_session.rollback()

    assert set((await async_session.exec(select(Flow.id))).all()) == {target_flow_id, unrelated_flow_id}
    assert set((await async_session.exec(select(TraceTable.id))).all()) == {target_trace_id, unrelated_trace_id}
    assert set((await async_session.exec(select(SpanTable.id))).all()) == {target_span_id, unrelated_span_id}

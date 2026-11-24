"""Regression test for https://github.com/langflow-ai/langflow/issues/13955.

"Clear all" traces (DELETE /api/v1/traces, `delete_traces_by_flow` in
api/v1/traces.py) issues a bulk `DELETE FROM trace WHERE flow_id = ...`. That
statement bypasses the ORM's `cascade="all, delete-orphan"` relationship on
`TraceTable.spans` (which only fires through `session.delete()`), so on a
database that enforces foreign keys, the delete used to fail with e.g.:

    IntegrityError: FOREIGN KEY constraint failed

whenever a trace still had spans referencing it. The fix adds
`ondelete="CASCADE"` to the `span.trace_id` foreign key at the database level,
so the cascade happens regardless of how the DELETE was issued.
"""

from __future__ import annotations

import pytest
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.traces.model import SpanTable, TraceTable
from sqlalchemy import delete, event
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession


@pytest.fixture(name="fk_enforced_engine")
async def _fk_enforced_engine():
    """Async in-memory SQLite engine with FK constraints enforced.

    SQLite does not enforce foreign keys unless PRAGMA foreign_keys=ON is set
    per connection. Enabling it here lets ON DELETE CASCADE actually run, so
    this test exercises the same constraint-enforcement behavior Postgres
    applies in production.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):  # noqa: ARG001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await engine.dispose()


@pytest.mark.asyncio
class TestSpanCascadeDeleteOnBulkTraceDelete:
    async def _seed_flow_trace_span(self, session: AsyncSession):
        flow = Flow(name="f", description="test", data={})
        session.add(flow)
        await session.commit()
        await session.refresh(flow)

        trace = TraceTable(name="t", flow_id=flow.id, session_id="s")
        session.add(trace)
        await session.commit()
        await session.refresh(trace)

        span = SpanTable(name="s", trace_id=trace.id)
        session.add(span)
        await session.commit()
        await session.refresh(span)

        return flow, trace, span

    async def test_bulk_delete_of_trace_cascades_to_spans(self, fk_enforced_engine):
        async with AsyncSession(fk_enforced_engine, expire_on_commit=False) as session:
            flow, _trace, span = await self._seed_flow_trace_span(session)
            span_id = span.id

            # Same bulk statement delete_traces_by_flow executes in
            # api/v1/traces.py: `sa.delete(TraceTable).where(TraceTable.flow_id == flow_id)`.
            # This must not raise an IntegrityError even though a span still
            # references the trace being deleted.
            await session.execute(delete(TraceTable).where(TraceTable.flow_id == flow.id))
            await session.commit()

        async with AsyncSession(fk_enforced_engine, expire_on_commit=False) as fresh:
            assert await fresh.get(TraceTable, _trace.id) is None
            assert await fresh.get(SpanTable, span_id) is None

    async def test_bulk_delete_of_trace_without_spans_still_works(self, fk_enforced_engine):
        async with AsyncSession(fk_enforced_engine, expire_on_commit=False) as session:
            flow = Flow(name="f", description="test", data={})
            session.add(flow)
            await session.commit()
            await session.refresh(flow)

            trace = TraceTable(name="t", flow_id=flow.id, session_id="s")
            session.add(trace)
            await session.commit()
            await session.refresh(trace)
            trace_id = trace.id

            await session.execute(delete(TraceTable).where(TraceTable.flow_id == flow.id))
            await session.commit()

        async with AsyncSession(fk_enforced_engine, expire_on_commit=False) as fresh:
            assert await fresh.get(TraceTable, trace_id) is None

"""Verify native tracing writes parent links under PostgreSQL foreign keys."""

import os
from contextlib import asynccontextmanager
from uuid import uuid4

import pytest
from langflow.services.database.models import Flow, Folder, SpanTable, TraceTable, User
from langflow.services.tracing.native import NativeTracer
from lfx.services import deps
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.schema import CreateSchema, DropSchema
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

pytestmark = [pytest.mark.noclient, pytest.mark.no_blockbuster]


async def test_native_flush_preserves_valid_parent_links(monkeypatch):
    url = os.environ.get("LANGFLOW_TEST_DATABASE_URI")
    if not url or not url.startswith("postgresql+psycopg://"):
        pytest.skip("LANGFLOW_TEST_DATABASE_URI must point to a PostgreSQL test cluster")

    schema = "native_trace_" + uuid4().hex
    engine = create_async_engine(url, execution_options={"schema_translate_map": {None: schema}})

    @asynccontextmanager
    async def session_scope():
        async with AsyncSession(engine) as session:
            yield session
            await session.commit()

    monkeypatch.setattr(deps, "session_scope", session_scope)
    monkeypatch.setenv("LANGFLOW_NATIVE_TRACING", "true")

    try:
        async with engine.begin() as connection:
            await connection.execute(CreateSchema(schema))
            # Create only the tracing tables and the tables they reference.
            tables = [User.__table__, Folder.__table__, Flow.__table__, TraceTable.__table__, SpanTable.__table__]
            await connection.run_sync(lambda sync: SQLModel.metadata.create_all(sync, tables=tables))

        flow_id, trace_id = uuid4(), uuid4()
        async with session_scope() as session:
            session.add(Flow(id=flow_id, name="Native tracing PostgreSQL test"))

        tracer = NativeTracer("Native tracing PostgreSQL test", "chain", "test", trace_id, flow_id=str(flow_id))
        root, child, grandchild, orphan, missing, cycle_a, cycle_b = (uuid4() for _ in range(7))
        batch = [
            (grandchild, child),
            (orphan, missing),
            (child, root),
            (cycle_a, cycle_b),
            (cycle_b, cycle_a),
            (root, None),
        ]
        for span_id, parent_id in batch:
            tracer.add_langchain_span(span_id, str(span_id), "chain", {}, parent_span_id=parent_id)
            tracer.end_langchain_span(span_id)

        tracer.end({}, {})
        await tracer.wait_for_flush()

        # A fresh session verifies the trace and all six spans were committed.
        async with AsyncSession(engine) as session:
            trace = await session.get(TraceTable, trace_id)
            assert trace is not None
            assert trace.flow_id == flow_id
            spans = (await session.exec(select(SpanTable).where(SpanTable.trace_id == trace_id))).all()
            assert {span.id: span.parent_span_id for span in spans} == {
                root: None,
                child: root,
                grandchild: child,
                orphan: None,
                cycle_a: None,
                cycle_b: None,
            }
    finally:
        try:
            async with engine.begin() as connection:
                await connection.execute(DropSchema(schema, cascade=True, if_exists=True))
        finally:
            await engine.dispose()

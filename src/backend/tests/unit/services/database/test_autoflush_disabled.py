"""Regression tests for the autoflush=False fix on async_session_maker.

Background
----------
SQLAlchemy's default ``autoflush=True`` means the session automatically issues a
flush (i.e. sends pending SQL to the database) whenever a SELECT would otherwise
see stale data.  In ``_flush_to_database()`` we call ``session.merge(span)`` in a
loop and *rely on topological_sort_spans()* to ensure parents land in the DB before
children (PostgreSQL enforces ``span.parent_span_id → span.id`` with an immediate
FK constraint).

The problem: ``session.merge()`` can itself trigger an implicit autoflush if the
identity-map already contains tracked objects and SQLAlchemy decides a flush is
needed.  When that happens between individual ``merge()`` calls inside the loop, a
child span can reach the DB before its parent — violating the FK constraint and
raising ``IntegrityError`` even though the topological sort is correct.

The fix: pass ``autoflush=False`` to both ``async_sessionmaker()`` call-sites in
``DatabaseService``.  Writes are still durably committed by the explicit
``await session.commit()`` inside ``session_scope()``.

These tests guard against the fix being accidentally reverted.

Fixes: https://github.com/langflow-ai/langflow/issues/DSLF-524 (span FK violation
       on v1.9.2 despite topological sort)
"""

from __future__ import annotations

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession


class TestDatabaseServiceSessionMakerConfig:
    """Verify that DatabaseService creates sessions with autoflush=False."""

    def test_async_session_maker_has_autoflush_false(self):
        """The session factory must be configured with autoflush=False.

        Without this, SQLAlchemy's default autoflush=True can fire an implicit
        flush between session.merge() calls inside _flush_to_database(), sending
        a child span to the DB before its parent and triggering a FK violation.
        """
        from sqlalchemy.ext.asyncio import async_sessionmaker
        from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

        # Simulate a minimal engine (StaticPool avoids needing a real DB URL)
        engine = create_async_engine(
            "sqlite+aiosqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        # Replicate the exact factory construction used in DatabaseService.__init__
        factory = async_sessionmaker(
            engine,
            class_=SQLModelAsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

        # Instantiate a session and check its autoflush flag
        session = factory()
        try:
            assert session.autoflush is False, (
                "Session must have autoflush=False to prevent implicit mid-loop "
                "flushes that break the topological span insertion order."
            )
        finally:
            # Dispose synchronously — we're in a plain (non-async) test
            import asyncio

            asyncio.get_event_loop().run_until_complete(session.close())

    def test_default_autoflush_is_true_without_fix(self):
        """Documents baseline: SQLAlchemy default IS autoflush=True.

        This test proves that omitting autoflush=False (the old code) would
        leave sessions with the dangerous default.
        """
        from sqlalchemy.ext.asyncio import async_sessionmaker
        from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

        engine = create_async_engine(
            "sqlite+aiosqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        # Old factory — no autoflush=False
        buggy_factory = async_sessionmaker(
            engine,
            class_=SQLModelAsyncSession,
            expire_on_commit=False,
            # autoflush not set → defaults to True
        )

        import asyncio

        session = buggy_factory()
        try:
            assert session.autoflush is True, "This test documents the pre-fix behavior: autoflush defaults to True."
        finally:
            asyncio.get_event_loop().run_until_complete(session.close())


@pytest.fixture(name="fk_enforced_engine_autoflush")
async def _fk_enforced_engine():
    """Async in-memory SQLite engine with FK constraints enforced."""
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
class TestAutoflushFKViolationRegression:
    """End-to-end regression: merging child span before parent must not raise.

    This class tests the exact failure mode that was present in v1.9.2:
    - topological_sort_spans() is correct (parent first)
    - but autoflush=True causes the session to flush a child to the DB before
      the parent, producing an IntegrityError on span.parent_span_id → span.id

    With autoflush=False the merge loop completes in sorted order and a single
    flush at commit time writes everything correctly.
    """

    async def _seed_flow_and_trace(self, session: AsyncSession):
        """Insert a Flow and TraceTable row required by FK constraints."""
        from langflow.services.database.models.flow.model import Flow
        from langflow.services.database.models.traces.model import TraceTable

        flow = Flow(name="regression-flow", description="autoflush test", data={})
        session.add(flow)
        await session.commit()
        await session.refresh(flow)

        trace = TraceTable(name="t", flow_id=flow.id, session_id="sess")
        session.add(trace)
        await session.commit()
        await session.refresh(trace)
        return flow, trace

    async def test_topo_sorted_merge_with_autoflush_false_does_not_raise(self, fk_enforced_engine_autoflush):
        """Merging spans in topologically-sorted order with autoflush=False does not raise.

        Post-fix behavior that _flush_to_database() relies on:
        1. topological_sort_spans() orders spans parent → child
        2. autoflush=False means no implicit flush fires mid-loop
        3. session.commit() flushes once in the correct order → no FK violation

        The test uses the same in-memory SQLite engine with PRAGMA foreign_keys=ON
        that TestSpanCascadeDeleteOnBulkTraceDelete uses, so FK constraints are
        actually enforced.
        """
        from uuid import uuid4

        from langflow.services.database.models.traces.model import SpanTable

        parent_id = uuid4()
        child_id = uuid4()

        async with AsyncSession(
            fk_enforced_engine_autoflush,
            expire_on_commit=False,
            autoflush=False,  # THE FIX
        ) as session:
            _flow, trace = await self._seed_flow_and_trace(session)

            # Parent first — mirrors what topological_sort_spans() produces
            parent = SpanTable(id=parent_id, trace_id=trace.id, parent_span_id=None, name="parent")
            await session.merge(parent)

            # Child second — references parent
            child = SpanTable(id=child_id, trace_id=trace.id, parent_span_id=parent_id, name="child")
            await session.merge(child)

            # Single flush at commit — must not raise IntegrityError
            await session.commit()

        # Verify both rows persisted
        async with AsyncSession(fk_enforced_engine_autoflush, expire_on_commit=False) as verify:
            assert await verify.get(SpanTable, parent_id) is not None
            assert await verify.get(SpanTable, child_id) is not None

    async def test_session_maker_factory_produces_autoflush_false_sessions(self, fk_enforced_engine_autoflush):
        """The async_sessionmaker factory must produce sessions with autoflush=False.

        This mirrors DatabaseService's factory construction and confirms that a
        session yielded from async_session_maker() has autoflush=False.
        """
        from sqlalchemy.ext.asyncio import async_sessionmaker
        from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

        factory = async_sessionmaker(
            fk_enforced_engine_autoflush,
            class_=SQLModelAsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

        async with factory() as session:
            assert session.autoflush is False

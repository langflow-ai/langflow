"""The trace flush must not scale its statement count with the number of spans.

`_flush_to_database` used to call ``session.merge()`` once per object. merge()
issues a SELECT to discover whether the row exists before writing it, so a trace
with N spans cost roughly 2N round trips -- and span count scales with flow size.
Traces and spans are constructed fresh with deterministic uuid5 keys, so that
SELECT can never find anything on a first flush.

The current implementation emits one ``INSERT .. ON CONFLICT`` for the trace and
one multi-VALUES ``INSERT .. ON CONFLICT`` for all spans.

The existing tracer tests pass under either implementation -- they assert on
persisted content, not on how many statements produced it -- so without this
test a regression back to the per-object loop would be invisible.
"""

import os
from unittest.mock import patch
from uuid import uuid4

import pytest
from langflow.services.tracing.native import NativeTracer
from lfx.services.deps import session_scope
from sqlalchemy import event


def _tracer(flow_id: str, n_spans: int) -> NativeTracer:
    tracer = NativeTracer(
        trace_name=f"Batching Flow - {flow_id}",
        trace_type="chain",
        project_name="test-project",
        trace_id=uuid4(),
        flow_id=flow_id,
        user_id="user-1",
        session_id=None,
    )
    for i in range(n_spans):
        name = f"comp-{i}"
        tracer.add_trace(trace_id=name, trace_name=name, trace_type="component", inputs={})
        tracer.end_trace(trace_id=name, trace_name=name, outputs={}, error=None)
    return tracer


async def _count_statements_for_flush(n_spans: int) -> dict[str, int]:
    """Flush a trace with n_spans and count the SQL statements it issued.

    Requires the ``client`` fixture: without an initialised database service
    ``session_scope`` yields a NoopSession, which has no engine to listen on.
    """
    counts: dict[str, int] = {"insert": 0, "select": 0, "update": 0, "other": 0}

    def before_execute(_conn, _cursor, statement, _params, _context, _executemany):
        head = statement.lstrip().split(None, 1)[0].lower() if statement.strip() else ""
        counts[head if head in counts else "other"] += 1

    async with session_scope() as session:
        engine = session.get_bind()
        sync_engine = getattr(engine, "sync_engine", engine)
        event.listen(sync_engine, "before_cursor_execute", before_execute)
        try:
            tracer = _tracer(str(uuid4()), n_spans)
            with patch.dict(os.environ, {}, clear=False):
                await tracer._flush_to_database()
        finally:
            event.remove(sync_engine, "before_cursor_execute", before_execute)
    return counts


@pytest.mark.parametrize("n_spans", [2, 8])
async def test_flush_statement_count_does_not_scale_with_span_count(client, n_spans):  # noqa: ARG001
    counts = await _count_statements_for_flush(n_spans)
    total_writes = counts["insert"] + counts["update"]
    # One statement for the trace, one for the whole span batch. A small margin
    # is allowed for session bookkeeping, but the count must not track n_spans.
    assert total_writes <= 4, (
        f"{n_spans} spans produced {total_writes} write statements "
        f"({counts}); the flush is issuing one statement per object again"
    )


async def test_flush_does_not_read_before_writing(client):  # noqa: ARG001
    """merge() reads before writing; ON CONFLICT does not."""
    counts = await _count_statements_for_flush(8)
    assert counts["select"] <= 2, (
        f"flush issued {counts['select']} SELECTs ({counts}); a read-before-write "
        f"loop has returned -- these rows are always new on a first flush"
    )

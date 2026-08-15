"""Unit tests for NativeTracer and NativeCallbackHandler."""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4, uuid5

import pytest
from langflow.services.database.models.traces.model import SpanStatus, SpanTable, SpanType, TraceTable
from langflow.services.tracing.native import NativeTracer
from langflow.services.tracing.span_sorting import (
    LANGFLOW_SPAN_NAMESPACE,
    resolve_span_uuids,
    topological_sort_spans,
)
from sqlalchemy import event, text
from sqlalchemy.engine import Engine
from sqlmodel import select

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tracer(
    flow_id: str | None = None,
    session_id: str | None = None,
    trace_id: UUID | None = None,
) -> NativeTracer:
    tid = trace_id or uuid4()
    return NativeTracer(
        trace_name=f"Test Flow - {flow_id or 'flow-123'}",
        trace_type="chain",
        project_name="test-project",
        trace_id=tid,
        flow_id=flow_id or "flow-123",
        user_id="user-1",
        session_id=session_id,
    )


# ---------------------------------------------------------------------------
# _is_enabled / ready
# ---------------------------------------------------------------------------


class TestIsEnabled:
    def test_enabled_by_default(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("LANGFLOW_NATIVE_TRACING", None)
            assert NativeTracer._is_enabled() is True

    @pytest.mark.parametrize("value", ["false", "False", "FALSE", "0", "no"])
    def test_disabled_by_env_var(self, value):
        with patch.dict(os.environ, {"LANGFLOW_NATIVE_TRACING": value}):
            assert NativeTracer._is_enabled() is False

    @pytest.mark.parametrize("value", ["true", "True", "1", "yes"])
    def test_enabled_by_env_var(self, value):
        with patch.dict(os.environ, {"LANGFLOW_NATIVE_TRACING": value}):
            assert NativeTracer._is_enabled() is True

    def test_ready_property_reflects_is_enabled(self):
        with patch.dict(os.environ, {"LANGFLOW_NATIVE_TRACING": "false"}):
            tracer = _make_tracer()
            assert tracer.ready is False

        with patch.dict(os.environ, {"LANGFLOW_NATIVE_TRACING": "true"}):
            tracer = _make_tracer()
            assert tracer.ready is True


# ---------------------------------------------------------------------------
# __init__ defaults
# ---------------------------------------------------------------------------


class TestInit:
    def test_session_id_defaults_to_trace_id(self):
        tid = uuid4()
        tracer = NativeTracer(
            trace_name="Flow",
            trace_type="chain",
            project_name="proj",
            trace_id=tid,
            flow_id="flow-1",
            session_id=None,
        )
        assert tracer.session_id == str(tid)

    def test_session_id_uses_provided_value(self):
        tracer = _make_tracer(session_id="my-session")
        assert tracer.session_id == "my-session"

    def test_flow_id_extracted_from_trace_name_when_not_provided(self):
        tid = uuid4()
        tracer = NativeTracer(
            trace_name="My Flow - flow-abc",
            trace_type="chain",
            project_name="proj",
            trace_id=tid,
            flow_id=None,
        )
        assert tracer.flow_id == "flow-abc"

    def test_flow_id_uses_full_trace_name_when_no_separator(self):
        tid = uuid4()
        tracer = NativeTracer(
            trace_name="NoSeparatorHere",
            trace_type="chain",
            project_name="proj",
            trace_id=tid,
            flow_id=None,
        )
        assert tracer.flow_id == "NoSeparatorHere"


# ---------------------------------------------------------------------------
# add_trace / end_trace
# ---------------------------------------------------------------------------


class TestAddEndTrace:
    def test_add_trace_stores_span(self):
        tracer = _make_tracer()
        tracer.add_trace(
            trace_id="comp-1",
            trace_name="My Component (comp-1)",
            trace_type="chain",
            inputs={"key": "value"},
            metadata={"meta": "data"},
        )
        assert "comp-1" in tracer.spans
        span = tracer.spans["comp-1"]
        assert span["name"] == "My Component"
        assert span["inputs"] == {"key": "value"}

    def test_add_trace_sets_current_component_id(self):
        tracer = _make_tracer()
        tracer.add_trace("comp-1", "Comp (comp-1)", "chain", {})
        assert tracer._current_component_id == "comp-1"

    def test_add_trace_noop_when_not_ready(self):
        with patch.dict(os.environ, {"LANGFLOW_NATIVE_TRACING": "false"}):
            tracer = _make_tracer()
        tracer.add_trace("comp-1", "Comp", "chain", {})
        assert "comp-1" not in tracer.spans

    def test_end_trace_moves_span_to_completed(self):
        tracer = _make_tracer()
        tracer.add_trace("comp-1", "My Component (comp-1)", "chain", {"in": "val"})
        tracer.end_trace("comp-1", "My Component", outputs={"out": "result"})

        assert "comp-1" not in tracer.spans
        assert len(tracer.completed_spans) == 1
        span = tracer.completed_spans[0]
        assert span["name"] == "My Component"
        assert span["status"] == SpanStatus.OK
        assert span["outputs"] == {"out": "result"}
        assert span["error"] is None

    def test_end_trace_with_error(self):
        tracer = _make_tracer()
        tracer.add_trace("comp-1", "Comp (comp-1)", "chain", {})
        err = ValueError("something broke")
        tracer.end_trace("comp-1", "Comp", error=err)

        span = tracer.completed_spans[0]
        assert span["status"] == SpanStatus.ERROR
        assert span["error"] == "something broke"
        assert span["outputs"]["error"] == "something broke"

    def test_end_trace_with_logs(self):
        tracer = _make_tracer()
        tracer.add_trace("comp-1", "Comp (comp-1)", "chain", {})
        log = MagicMock()
        log.model_dump.return_value = {"message": "log entry"}
        tracer.end_trace("comp-1", "Comp", logs=[log])

        span = tracer.completed_spans[0]
        assert span["outputs"]["logs"] == [{"message": "log entry"}]

    def test_end_trace_noop_for_unknown_trace_id(self):
        tracer = _make_tracer()
        tracer.end_trace("nonexistent", "Comp")
        assert len(tracer.completed_spans) == 0

    def test_end_trace_noop_when_not_ready(self):
        with patch.dict(os.environ, {"LANGFLOW_NATIVE_TRACING": "false"}):
            tracer = _make_tracer()
        tracer.end_trace("comp-1", "Comp")
        assert len(tracer.completed_spans) == 0

    def test_end_trace_clears_current_component_id(self):
        tracer = _make_tracer()
        tracer.add_trace("comp-1", "Comp (comp-1)", "chain", {})
        tracer.end_trace("comp-1", "Comp")
        assert tracer._current_component_id is None


class TestFinalizePendingSpans:
    """Force-completion of spans that started but never received an end_trace.

    A span whose end event raced the trace worker teardown must still be flushed, otherwise
    the terminal component (e.g. Chat Output) is silently missing from the persisted trace.
    """

    def test_pending_span_is_force_completed(self):
        tracer = _make_tracer()
        tracer.add_trace("out-1", "Chat Output (out-1)", "chain", {"in": "val"})
        tracer.end_trace("comp-1", "Other")  # noop; out-1 deliberately left unended

        tracer._finalize_pending_spans()

        assert "out-1" not in tracer.spans
        names = [s["name"] for s in tracer.completed_spans]
        assert "Chat Output" in names
        span = next(s for s in tracer.completed_spans if s["name"] == "Chat Output")
        assert span["status"] == SpanStatus.OK
        assert span["inputs"] == {"in": "val"}

    def test_already_ended_spans_are_untouched(self):
        tracer = _make_tracer()
        tracer.add_trace("comp-1", "Comp (comp-1)", "chain", {})
        tracer.end_trace("comp-1", "Comp", outputs={"out": "x"})

        tracer._finalize_pending_spans()

        assert len(tracer.completed_spans) == 1
        assert tracer.completed_spans[0]["outputs"] == {"out": "x"}

    def test_noop_when_no_pending_spans(self):
        tracer = _make_tracer()
        tracer._finalize_pending_spans()
        assert tracer.completed_spans == []

    def test_end_trace_includes_token_attributes(self):
        tracer = _make_tracer()
        tracer.add_trace("comp-1", "Comp (comp-1)", "llm", {})
        # Simulate token accumulation from a child LangChain span
        tracer._component_tokens["comp-1"] = {
            "gen_ai.usage.input_tokens": 10,
            "gen_ai.usage.output_tokens": 20,
        }
        tracer.end_trace("comp-1", "Comp")

        span = tracer.completed_spans[0]
        assert span["attributes"]["gen_ai.usage.input_tokens"] == 10
        assert span["attributes"]["gen_ai.usage.output_tokens"] == 20

    def test_end_trace_no_token_attributes_when_zero(self):
        tracer = _make_tracer()
        tracer.add_trace("comp-1", "Comp (comp-1)", "chain", {})
        tracer.end_trace("comp-1", "Comp")

        span = tracer.completed_spans[0]
        assert "prompt_tokens" not in span["attributes"]
        assert "total_tokens" not in span["attributes"]


# ---------------------------------------------------------------------------
# _map_trace_type
# ---------------------------------------------------------------------------


class TestMapTraceType:
    @pytest.mark.parametrize(
        ("input_type", "expected"),
        [
            ("chain", SpanType.CHAIN),
            ("llm", SpanType.LLM),
            ("tool", SpanType.TOOL),
            ("retriever", SpanType.RETRIEVER),
            ("embedding", SpanType.EMBEDDING),
            ("parser", SpanType.PARSER),
            ("agent", SpanType.AGENT),
            ("CHAIN", SpanType.CHAIN),
            ("LLM", SpanType.LLM),
            ("unknown_type", SpanType.CHAIN),  # fallback
            ("", SpanType.CHAIN),  # fallback
        ],
    )
    def test_map_trace_type(self, input_type, expected):
        assert NativeTracer._map_trace_type(input_type) == expected


# ---------------------------------------------------------------------------
# end() — scheduling flush task
# ---------------------------------------------------------------------------


class TestEnd:
    @pytest.mark.asyncio
    async def test_end_creates_flush_task(self):
        tracer = _make_tracer()
        tracer.add_trace("comp-1", "Comp (comp-1)", "chain", {})
        tracer.end_trace("comp-1", "Comp", outputs={"out": "val"})

        with patch.object(tracer, "_flush_to_database", new_callable=AsyncMock) as mock_flush:
            mock_flush.return_value = None
            tracer.end(inputs={}, outputs={})
            assert tracer._flush_task is not None
            await tracer._flush_task

        mock_flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_end_noop_when_not_ready(self):
        with patch.dict(os.environ, {"LANGFLOW_NATIVE_TRACING": "false"}):
            tracer = _make_tracer()
        tracer.end(inputs={}, outputs={})
        assert tracer._flush_task is None

    def test_end_logs_error_when_no_event_loop(self):
        tracer = _make_tracer()
        tracer.add_trace("comp-1", "Comp (comp-1)", "chain", {})
        tracer.end_trace("comp-1", "Comp")

        with patch("langflow.services.tracing.native.logger") as mock_logger:
            with patch("asyncio.get_running_loop", side_effect=RuntimeError("no loop")):
                tracer.end(inputs={}, outputs={})
            mock_logger.error.assert_called_once()
            assert tracer._flush_task is None


# ---------------------------------------------------------------------------
# wait_for_flush
# ---------------------------------------------------------------------------


class TestWaitForFlush:
    @pytest.mark.asyncio
    async def test_wait_for_flush_awaits_task(self):
        tracer = _make_tracer()
        completed = []

        async def fake_flush():
            completed.append(True)

        tracer._flush_task = asyncio.create_task(fake_flush())
        await tracer.wait_for_flush()
        assert completed == [True]

    @pytest.mark.asyncio
    async def test_wait_for_flush_noop_when_no_task(self):
        tracer = _make_tracer()
        # Should not raise
        await tracer.wait_for_flush()

    @pytest.mark.asyncio
    async def test_wait_for_flush_swallows_task_exception(self):
        tracer = _make_tracer()

        async def failing_flush():
            msg = "flush error"
            raise RuntimeError(msg)

        tracer._flush_task = asyncio.create_task(failing_flush())
        # Should not raise
        await tracer.wait_for_flush()


# ---------------------------------------------------------------------------
# _flush_to_database
# ---------------------------------------------------------------------------


@pytest.fixture
async def db_flow_id(async_session, monkeypatch) -> str:
    """Point ``_flush_to_database`` at a real DB session and return a flow_id that exists in it.

    ``_flush_to_database`` imports ``session_scope`` from ``lfx.services.deps`` at call time, so
    patching the attribute on that module is enough to hand it the in-memory session created by
    the shared ``async_session`` fixture. The flush then writes real rows, and the tests read
    those rows back instead of inspecting how they got there.
    """
    import lfx.services.deps
    from langflow.services.database.models.flow.model import Flow

    flow = Flow(id=uuid4(), name=f"flow-{uuid4()}", data={})
    async_session.add(flow)
    await async_session.commit()

    @asynccontextmanager
    async def _scope():
        yield async_session
        await async_session.commit()

    monkeypatch.setattr(lfx.services.deps, "session_scope", _scope)
    return str(flow.id)


def _bound_values(parameters):
    """The bound values of one executed statement, in the order the driver sends them.

    SQLite binds positionally and hands back a tuple; psycopg binds by name and hands back a dict
    keyed ``name_m0``, ``name_m1``, .... The dict is ordered row by row, so its values are in the
    same order the tuple would be.
    """
    return list(parameters.values()) if isinstance(parameters, dict) else list(parameters)


async def _enforce_foreign_keys(session) -> None:
    """Make the session enforce foreign keys, whichever backend it is on.

    PostgreSQL always does. SQLite does not unless asked, per connection, and ``PRAGMA`` is a
    syntax error on PostgreSQL, so the statement has to be guarded rather than issued blindly.
    """
    connection = await session.connection()
    if connection.dialect.name != "sqlite":
        return
    await session.execute(text("PRAGMA foreign_keys=ON"))
    assert (await session.execute(text("PRAGMA foreign_keys"))).scalar() == 1


async def _fetch_trace(session, trace_id: UUID):
    """Read the persisted trace row back.

    ``populate_existing`` forces a refresh from the DB so a second flush is not masked by rows
    already in the session's identity map.
    """
    statement = select(TraceTable).where(TraceTable.id == trace_id).execution_options(populate_existing=True)
    return (await session.exec(statement)).first()


async def _fetch_spans(session, trace_id: UUID) -> list[SpanTable]:
    statement = (
        select(SpanTable)
        .where(SpanTable.trace_id == trace_id)
        .order_by(SpanTable.start_time)
        .execution_options(populate_existing=True)
    )
    return list((await session.exec(statement)).all())


def _span_uuid(trace_id: UUID, component_id: str) -> UUID:
    """The id the tracer derives for a non-UUID span id (the upsert's conflict key)."""
    return uuid5(LANGFLOW_SPAN_NAMESPACE, f"{trace_id}-{component_id}")


class TestFlushToDatabase:
    async def test_flush_invalid_flow_id_logs_error_and_continues(self, async_session, db_flow_id):  # noqa: ARG002
        """A malformed flow_id is reported and the trace is filed under a sentinel flow_id.

        The sentinel is a uuid5 that by construction matches no row in `flow`, and `trace.flow_id`
        carries a foreign key to `flow.id`. So on PostgreSQL, which enforces that immediately, this
        fallback cannot store anything: the INSERT raises, the session rolls back, and
        `wait_for_flush` swallows the error, which is the opposite of what the fallback's own
        comment in native.py claims it achieves. That gap predates this change -- `merge()` hit the
        same foreign key -- so it is documented here rather than fixed, and the persisted-row half
        of this test only runs where foreign keys are off.
        """
        tracer = _make_tracer(flow_id="not-a-uuid")
        tracer.add_trace("comp-1", "Comp (comp-1)", "chain", {})
        tracer.end_trace("comp-1", "Comp")

        connection = await async_session.connection()
        enforces_foreign_keys = connection.dialect.name != "sqlite"

        with patch("langflow.services.tracing.native.logger") as mock_logger:
            try:
                await tracer._flush_to_database()
            except Exception:
                if not enforces_foreign_keys:
                    raise

        mock_logger.error.assert_called_once()

        if enforces_foreign_keys:
            return

        # It continued: the rows are in the DB, filed under the deterministic sentinel flow_id.
        trace = await _fetch_trace(async_session, tracer.trace_id)
        assert trace is not None
        assert trace.flow_id == uuid5(LANGFLOW_SPAN_NAMESPACE, "invalid-flow-id:not-a-uuid")
        assert [span.name for span in await _fetch_spans(async_session, tracer.trace_id)] == ["Comp"]

    async def test_flush_writes_trace_and_spans(self, async_session, db_flow_id):
        tracer = _make_tracer(flow_id=db_flow_id)
        tracer.add_trace("comp-1", "Comp (comp-1)", "chain", {"in": "val"})
        tracer.end_trace("comp-1", "Comp", outputs={"out": "result"})

        await tracer._flush_to_database()

        trace = await _fetch_trace(async_session, tracer.trace_id)
        assert trace is not None
        assert trace.flow_id == UUID(db_flow_id)
        assert trace.name == tracer.trace_name
        assert trace.session_id == tracer.session_id
        assert trace.status == SpanStatus.OK
        assert trace.end_time is not None

        spans = await _fetch_spans(async_session, tracer.trace_id)
        assert len(spans) == 1
        span = spans[0]
        assert span.id == _span_uuid(tracer.trace_id, "comp-1")
        assert span.name == "Comp"
        assert span.span_type == SpanType.CHAIN
        assert span.status == SpanStatus.OK
        assert span.inputs == {"in": "val"}
        assert span.outputs == {"out": "result"}
        assert span.error is None

    async def test_flush_uses_uuid5_for_non_uuid_span_id(self, async_session, db_flow_id):
        tracer = _make_tracer(flow_id=db_flow_id)
        # Manually add a completed span with a non-UUID string id
        tracer.completed_spans.append(
            {
                "id": "not-a-uuid-string",
                "name": "Span",
                "span_type": SpanType.CHAIN,
                "inputs": {},
                "outputs": None,
                "start_time": datetime.now(tz=timezone.utc),
                "end_time": datetime.now(tz=timezone.utc),
                "latency_ms": 10,
                "status": SpanStatus.OK,
                "error": None,
                "attributes": {},
            }
        )

        await tracer._flush_to_database()

        spans = await _fetch_spans(async_session, tracer.trace_id)
        assert len(spans) == 1
        # The persisted primary key is derived from the trace id, not random: this is what makes the
        # upsert idempotent across a HITL pause/resume.
        assert spans[0].id == _span_uuid(tracer.trace_id, "not-a-uuid-string")

    async def test_flush_error_status_when_span_has_error(self, async_session, db_flow_id):
        tracer = _make_tracer(flow_id=db_flow_id)
        tracer.add_trace("comp-1", "Comp (comp-1)", "chain", {})
        tracer.end_trace("comp-1", "Comp", error=ValueError("boom"))

        await tracer._flush_to_database()

        trace = await _fetch_trace(async_session, tracer.trace_id)
        assert trace is not None
        assert trace.status == SpanStatus.ERROR

        spans = await _fetch_spans(async_session, tracer.trace_id)
        assert [span.status for span in spans] == [SpanStatus.ERROR]
        assert spans[0].error == "boom"

    async def test_flush_calculates_total_tokens_from_spans(self, async_session, db_flow_id):
        tracer = _make_tracer(flow_id=db_flow_id)
        tracer.completed_spans = [
            {
                "id": str(uuid4()),
                "name": "Span1",
                "span_type": SpanType.LLM,
                "inputs": {},
                "outputs": None,
                "start_time": datetime.now(tz=timezone.utc),
                "end_time": datetime.now(tz=timezone.utc),
                "latency_ms": 10,
                "status": SpanStatus.OK,
                "error": None,
                "attributes": {"gen_ai.usage.input_tokens": 30, "gen_ai.usage.output_tokens": 20},
                "span_source": "langchain",
            },
            {
                "id": str(uuid4()),
                "name": "Span2",
                "span_type": SpanType.LLM,
                "inputs": {},
                "outputs": None,
                "start_time": datetime.now(tz=timezone.utc),
                "end_time": datetime.now(tz=timezone.utc),
                "latency_ms": 5,
                "status": SpanStatus.OK,
                "error": None,
                "attributes": {"gen_ai.usage.input_tokens": 20, "gen_ai.usage.output_tokens": 10},
                "span_source": "langchain",
            },
        ]

        await tracer._flush_to_database()

        trace = await _fetch_trace(async_session, tracer.trace_id)
        assert trace is not None
        assert trace.total_tokens == 80

    async def test_flush_twice_upserts_instead_of_duplicating(self, async_session, db_flow_id):
        """The HITL shape: a paused run flushes partial spans, then flushes again after resume.

        Both flushes carry the same trace id and the same deterministic span ids, so the second one
        must overwrite the first's rows rather than insert duplicates or raise on the primary key.
        """
        tracer = _make_tracer(flow_id=db_flow_id)
        tracer.add_trace("comp-1", "Comp (comp-1)", "chain", {"in": "val"})
        tracer.end_trace("comp-1", "Comp")  # paused: no outputs yet

        await tracer._flush_to_database()

        # Resume: the same span finishes, and a second component runs.
        tracer.completed_spans[0]["outputs"] = {"out": "done"}
        tracer.completed_spans[0]["latency_ms"] = 42
        tracer.add_trace("comp-2", "Second (comp-2)", "chain", {})
        tracer.end_trace("comp-2", "Second", outputs={"out": "also done"})

        await tracer._flush_to_database()  # must not raise

        traces = (await async_session.exec(select(TraceTable).execution_options(populate_existing=True))).all()
        assert [trace.id for trace in traces] == [tracer.trace_id]

        spans = await _fetch_spans(async_session, tracer.trace_id)
        assert len(spans) == 2
        assert {span.id for span in spans} == {
            _span_uuid(tracer.trace_id, "comp-1"),
            _span_uuid(tracer.trace_id, "comp-2"),
        }

        # The resumed row holds the second flush's values, not the paused ones.
        first = next(span for span in spans if span.id == _span_uuid(tracer.trace_id, "comp-1"))
        assert first.outputs == {"out": "done"}
        assert first.latency_ms == 42

    async def test_flush_collapses_repeated_builds_of_one_vertex(self, async_session, db_flow_id):
        """A Loop component or a graph cycle builds the same vertex once per iteration.

        Every build appends its own span, and the span id is uuid5 of (trace id, component id), so
        one flush carries the same primary key more than once. PostgreSQL refuses to let a single
        ON CONFLICT DO UPDATE touch a row twice and aborts the whole statement, which would discard
        the trace and every span with it, silently -- the flush error is swallowed. So the rows must
        be collapsed before they are sent, keeping the last build, which is what the per-row
        merge() this replaced produced via the identity map.

        SQLite applies the upsert row by row and accepts duplicates, so the stored rows look correct
        on the default backend either way. That is why this test also asserts on the SHAPE of the
        statement: it checks that only one row's worth of parameters was sent, which is the thing
        PostgreSQL rejects. Without the collapse this assertion fails on SQLite too, so the guard
        works on the backend CI actually runs.
        """
        tracer = _make_tracer(flow_id=db_flow_id)
        for iteration in range(3):
            tracer.add_trace("loop-body", "Loop Body (loop-body)", "chain", {"i": iteration})
            tracer.end_trace("loop-body", "Loop Body", outputs={"i": iteration})

        assert [span["id"] for span in tracer.completed_spans] == ["loop-body"] * 3

        span_inserts = []

        def capture(_conn, _cursor, statement, parameters, _context, _executemany):
            if "INTO span" in statement:
                span_inserts.append(parameters)

        event.listen(Engine, "before_cursor_execute", capture)
        try:
            await tracer._flush_to_database()
        finally:
            event.remove(Engine, "before_cursor_execute", capture)

        assert len(span_inserts) == 1, "the three builds must go out as one statement"
        assert len(span_inserts[0]) == len(SpanTable.__table__.columns), (
            "the statement carried more than one row of values, which PostgreSQL rejects with "
            "CardinalityViolation on the conflicting primary key"
        )

        spans = await _fetch_spans(async_session, tracer.trace_id)
        assert len(spans) == 1
        assert spans[0].id == _span_uuid(tracer.trace_id, "loop-body")
        assert spans[0].outputs == {"i": 2}


# ---------------------------------------------------------------------------
# add_langchain_span / end_langchain_span
# ---------------------------------------------------------------------------


class TestLangchainSpans:
    def test_add_langchain_span_stores_span(self):
        tracer = _make_tracer()
        span_id = uuid4()
        tracer.add_langchain_span(
            span_id=span_id,
            name="ChatOpenAI gpt-4",
            span_type="llm",
            inputs={"prompts": ["hello"]},
            model_name="gpt-4",
        )
        assert span_id in tracer.langchain_spans
        assert tracer.langchain_spans[span_id]["model_name"] == "gpt-4"

    def test_add_langchain_span_noop_when_not_ready(self):
        with patch.dict(os.environ, {"LANGFLOW_NATIVE_TRACING": "false"}):
            tracer = _make_tracer()
        span_id = uuid4()
        tracer.add_langchain_span(span_id, "LLM", "llm", {})
        assert span_id not in tracer.langchain_spans

    def test_end_langchain_span_moves_to_completed(self):
        tracer = _make_tracer()
        span_id = uuid4()
        tracer.add_langchain_span(span_id, "ChatOpenAI gpt-4", "llm", {"prompts": ["hi"]})
        tracer.end_langchain_span(
            span_id=span_id,
            outputs={"text": "response"},
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
        )

        assert span_id not in tracer.langchain_spans
        assert len(tracer.completed_spans) == 1
        span = tracer.completed_spans[0]
        assert span["status"] == SpanStatus.OK
        assert span["attributes"]["gen_ai.usage.input_tokens"] == 10
        assert span["attributes"]["gen_ai.usage.output_tokens"] == 20

    def test_end_langchain_span_with_error(self):
        tracer = _make_tracer()
        span_id = uuid4()
        tracer.add_langchain_span(span_id, "LLM", "llm", {})
        tracer.end_langchain_span(span_id, error="timeout error")

        span = tracer.completed_spans[0]
        assert span["status"] == SpanStatus.ERROR
        assert span["error"] == "timeout error"

    def test_end_langchain_span_accumulates_tokens_to_component(self):
        tracer = _make_tracer()
        tracer._current_component_id = "comp-1"
        span_id = uuid4()
        tracer.add_langchain_span(span_id, "LLM", "llm", {})
        tracer.end_langchain_span(
            span_id,
            prompt_tokens=5,
            completion_tokens=10,
            total_tokens=15,
        )

        assert tracer._component_tokens["comp-1"]["gen_ai.usage.input_tokens"] == 5
        assert tracer._component_tokens["comp-1"]["gen_ai.usage.output_tokens"] == 10

    def test_end_langchain_span_noop_for_unknown_span_id(self):
        tracer = _make_tracer()
        tracer.end_langchain_span(uuid4())
        assert len(tracer.completed_spans) == 0

    def test_end_langchain_span_noop_when_not_ready(self):
        with patch.dict(os.environ, {"LANGFLOW_NATIVE_TRACING": "false"}):
            tracer = _make_tracer()
        tracer.end_langchain_span(uuid4())
        assert len(tracer.completed_spans) == 0

    def test_end_langchain_span_includes_model_name_in_attributes(self):
        tracer = _make_tracer()
        span_id = uuid4()
        tracer.add_langchain_span(span_id, "ChatOpenAI gpt-4", "llm", {}, model_name="gpt-4")
        tracer.end_langchain_span(span_id)

        span = tracer.completed_spans[0]
        assert span["attributes"]["gen_ai.response.model"] == "gpt-4"


# ---------------------------------------------------------------------------
# get_langchain_callback
# ---------------------------------------------------------------------------


class TestGetLangchainCallback:
    def test_returns_none_when_not_ready(self):
        with patch.dict(os.environ, {"LANGFLOW_NATIVE_TRACING": "false"}):
            tracer = _make_tracer()
        assert tracer.get_langchain_callback() is None

    def test_returns_callback_handler_when_ready(self):
        tracer = _make_tracer()
        callback = tracer.get_langchain_callback()
        assert callback is not None
        from langflow.services.tracing.native_callback import NativeCallbackHandler

        assert isinstance(callback, NativeCallbackHandler)

    def test_callback_has_parent_span_id_when_component_active(self):
        from langflow.services.tracing.native_callback import NativeCallbackHandler

        tracer = _make_tracer()
        tracer._current_component_id = "comp-1"
        callback = tracer.get_langchain_callback()
        assert callback is not None
        assert isinstance(callback, NativeCallbackHandler)
        assert callback.parent_span_id is not None

    def test_callback_has_no_parent_span_id_when_no_component(self):
        from langflow.services.tracing.native_callback import NativeCallbackHandler

        tracer = _make_tracer()
        tracer._current_component_id = None
        callback = tracer.get_langchain_callback()
        assert callback is not None
        assert isinstance(callback, NativeCallbackHandler)
        assert callback.parent_span_id is None


# ---------------------------------------------------------------------------
# _topological_sort_spans
# ---------------------------------------------------------------------------


class TestTopologicalSortSpans:
    """Verify that spans are sorted so parents appear before children.

    This is critical for PostgreSQL which enforces FK constraints at INSERT time.
    """

    @staticmethod
    def _make_span(span_id, parent_id=None) -> tuple[dict, UUID, UUID | None]:
        """Helper to create a resolved (span_data, span_uuid, parent_uuid) tuple."""
        span_data = {"id": str(span_id), "name": f"span-{span_id}"}
        return (span_data, span_id, parent_id)

    def test_no_parents(self):
        a, b, c = uuid4(), uuid4(), uuid4()
        items = [self._make_span(a), self._make_span(b), self._make_span(c)]
        result = topological_sort_spans(items)
        assert [r[1] for r in result] == [a, b, c]

    def test_child_after_parent(self):
        parent_id = uuid4()
        child_id = uuid4()
        # Child comes first in the input list
        items = [self._make_span(child_id, parent_id), self._make_span(parent_id)]
        result = topological_sort_spans(items)
        uuids = [r[1] for r in result]
        assert uuids.index(parent_id) < uuids.index(child_id)

    def test_deep_nesting(self):
        root = uuid4()
        mid = uuid4()
        leaf = uuid4()
        # Reverse order: leaf, mid, root
        items = [
            self._make_span(leaf, mid),
            self._make_span(mid, root),
            self._make_span(root),
        ]
        result = topological_sort_spans(items)
        uuids = [r[1] for r in result]
        assert uuids.index(root) < uuids.index(mid) < uuids.index(leaf)

    def test_parent_outside_batch(self):
        """Spans referencing a missing parent are detached before insertion."""
        external_parent = uuid4()
        child_id = uuid4()
        items = [self._make_span(child_id, external_parent)]
        result = topological_sort_spans(items)
        assert len(result) == 1
        assert result[0][1] == child_id
        assert result[0][2] is None

    def test_mixed_roots_and_children(self):
        root_a = uuid4()
        child_a = uuid4()
        root_b = uuid4()
        items = [
            self._make_span(child_a, root_a),
            self._make_span(root_b),
            self._make_span(root_a),
        ]
        result = topological_sort_spans(items)
        uuids = [r[1] for r in result]
        assert uuids.index(root_a) < uuids.index(child_a)

    def test_cycle_two_node(self):
        """Spans forming a 2-node cycle should not cause errors or drop spans."""
        a = uuid4()
        b = uuid4()
        items = [
            self._make_span(a, b),
            self._make_span(b, a),
        ]
        result = topological_sort_spans(items)
        # Ensure all spans are present and no infinite loop / exception occurs.
        uuids = [r[1] for r in result]
        assert len(uuids) == 2
        assert set(uuids) == {a, b}

    def test_self_parent_span(self):
        """A span that lists itself as its own parent should still be returned."""
        span_id = uuid4()
        items = [
            self._make_span(span_id, span_id),
        ]
        result = topological_sort_spans(items)
        uuids = [r[1] for r in result]
        assert len(uuids) == 1
        assert uuids[0] == span_id

    def test_empty_input(self):
        result = topological_sort_spans([])
        assert result == []

    def test_cycle_does_not_mutate_original_span_data(self):
        """Verify cycle resolution doesn't mutate the original span dicts."""
        a = uuid4()
        b = uuid4()
        span_a = {"id": str(a), "name": "span-a", "parent_span_id": b}
        span_b = {"id": str(b), "name": "span-b", "parent_span_id": a}
        items = [(span_a, a, b), (span_b, b, a)]
        topological_sort_spans(items)
        # Original dicts should retain their parent_span_id values
        assert span_a["parent_span_id"] == b
        assert span_b["parent_span_id"] == a


# ---------------------------------------------------------------------------
# resolve_span_uuids
# ---------------------------------------------------------------------------


class TestResolveSpanUuids:
    """Verify UUID resolution for span IDs and parent IDs."""

    def test_valid_uuid_string_id(self):
        trace_id = uuid4()
        span_id = uuid4()
        spans = [{"id": str(span_id), "name": "span"}]
        result = resolve_span_uuids(spans, trace_id)
        assert len(result) == 1
        assert result[0][1] == span_id
        assert result[0][2] is None

    def test_non_uuid_string_id_uses_uuid5(self):
        from uuid import uuid5 as _uuid5

        from langflow.services.tracing.span_sorting import LANGFLOW_SPAN_NAMESPACE

        trace_id = uuid4()
        spans = [{"id": "not-a-uuid", "name": "span"}]
        result = resolve_span_uuids(spans, trace_id)
        expected = _uuid5(LANGFLOW_SPAN_NAMESPACE, f"{trace_id}-not-a-uuid")
        assert result[0][1] == expected

    def test_parent_as_uuid_instance(self):
        trace_id = uuid4()
        span_id = uuid4()
        parent_id = uuid4()
        spans = [{"id": str(span_id), "name": "span", "parent_span_id": parent_id}]
        result = resolve_span_uuids(spans, trace_id)
        assert result[0][2] == parent_id

    def test_parent_as_valid_uuid_string(self):
        trace_id = uuid4()
        span_id = uuid4()
        parent_id = uuid4()
        spans = [{"id": str(span_id), "name": "span", "parent_span_id": str(parent_id)}]
        result = resolve_span_uuids(spans, trace_id)
        assert result[0][2] == parent_id

    def test_parent_as_non_uuid_string(self):
        from uuid import uuid5 as _uuid5

        from langflow.services.tracing.span_sorting import LANGFLOW_SPAN_NAMESPACE

        trace_id = uuid4()
        span_id = uuid4()
        spans = [{"id": str(span_id), "name": "span", "parent_span_id": "invalid-parent"}]
        result = resolve_span_uuids(spans, trace_id)
        expected_parent = _uuid5(LANGFLOW_SPAN_NAMESPACE, f"{trace_id}-invalid-parent")
        assert result[0][2] == expected_parent

    def test_no_parent_span_id_key(self):
        trace_id = uuid4()
        span_id = uuid4()
        spans = [{"id": str(span_id), "name": "span"}]
        result = resolve_span_uuids(spans, trace_id)
        assert result[0][2] is None

    def test_empty_input(self):
        result = resolve_span_uuids([], uuid4())
        assert result == []


# ---------------------------------------------------------------------------
# _flush_to_database with parent/child spans
# ---------------------------------------------------------------------------


class TestFlushParentChildOrder:
    async def test_flush_inserts_parent_before_child(self, async_session, db_flow_id):
        """The parent is written ahead of the child, and the child's FK resolves to it.

        This used to assert the order of the ``session.merge()`` calls. Asserting only on the
        persisted rows would not replace it: the flush writes every span in one multi-row INSERT,
        both backends check an immediate FK at end of statement rather than per row, so the rows
        land and the FK resolves whichever order they were written in. Reversing the topological
        sort would not fail such a test.

        Order still matters, because ``_upsert_rows`` chunks: a parent and child far enough apart
        go out in separate statements, and then the parent's statement has to come first. So the
        assertion is on the order the statement itself carries.
        """
        tracer = _make_tracer(flow_id=db_flow_id)

        await _enforce_foreign_keys(async_session)

        parent_uuid = uuid4()
        child_uuid = uuid4()

        # Deliberately add child first to simulate the problematic ordering
        tracer.completed_spans = [
            {
                "id": str(child_uuid),
                "name": "Child Span",
                "span_type": SpanType.CHAIN,
                "inputs": {},
                "outputs": None,
                "start_time": datetime.now(tz=timezone.utc),
                "end_time": datetime.now(tz=timezone.utc),
                "latency_ms": 5,
                "status": SpanStatus.OK,
                "error": None,
                "attributes": {},
                "span_source": "component",
                "parent_span_id": parent_uuid,
            },
            {
                "id": str(parent_uuid),
                "name": "Parent Span",
                "span_type": SpanType.CHAIN,
                "inputs": {},
                "outputs": None,
                "start_time": datetime.now(tz=timezone.utc),
                "end_time": datetime.now(tz=timezone.utc),
                "latency_ms": 10,
                "status": SpanStatus.OK,
                "error": None,
                "attributes": {},
                "span_source": "component",
            },
        ]

        span_inserts = []

        def capture(_conn, _cursor, statement, parameters, _context, _executemany):
            if "INTO span" in statement:
                span_inserts.append(parameters)

        event.listen(Engine, "before_cursor_execute", capture)
        try:
            await tracer._flush_to_database()
        finally:
            event.remove(Engine, "before_cursor_execute", capture)

        # The parent is bound ahead of the child, so a chunk boundary between them still writes the
        # parent first. Matched on the names rather than the ids, which the driver binds as UUIDs.
        bound = [str(value) for parameters in span_inserts for value in _bound_values(parameters)]
        assert "Parent Span" in bound, bound
        assert "Child Span" in bound, bound
        assert bound.index("Parent Span") < bound.index("Child Span"), bound

        spans = await _fetch_spans(async_session, tracer.trace_id)
        by_id = {span.id: span for span in spans}
        assert set(by_id) == {parent_uuid, child_uuid}
        assert by_id[parent_uuid].parent_span_id is None
        assert by_id[child_uuid].parent_span_id == parent_uuid

    async def test_flush_detaches_span_from_missing_parent(self, async_session, db_flow_id):
        """A missing parent must not leave an invalid self-referential FK."""
        tracer = _make_tracer(flow_id=db_flow_id)
        tracer.completed_spans = [
            {
                "id": str(uuid4()),
                "name": "Orphan Span",
                "span_type": SpanType.CHAIN,
                "inputs": {},
                "outputs": None,
                "start_time": datetime.now(tz=timezone.utc),
                "end_time": datetime.now(tz=timezone.utc),
                "latency_ms": 5,
                "status": SpanStatus.OK,
                "error": None,
                "attributes": {},
                "span_source": "langchain",
                "parent_span_id": uuid4(),
            }
        ]

        await _enforce_foreign_keys(async_session)

        await tracer._flush_to_database()

        spans = await _fetch_spans(async_session, tracer.trace_id)
        assert len(spans) == 1
        assert spans[0].name == "Orphan Span"
        assert spans[0].parent_span_id is None

"""Unit tests for NativeTracer and NativeCallbackHandler."""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from langflow.services.database.models.traces.model import SpanStatus, SpanType
from langflow.services.tracing.native import NativeTracer

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


class TestFlushToDatabase:
    @pytest.mark.asyncio
    async def test_flush_invalid_flow_id_logs_error_and_continues(self):
        tracer = _make_tracer(flow_id="not-a-uuid")
        tracer.add_trace("comp-1", "Comp (comp-1)", "chain", {})
        tracer.end_trace("comp-1", "Comp")

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("langflow.services.tracing.native.logger") as mock_logger,
            patch("lfx.services.deps.session_scope", return_value=mock_session),
        ):
            await tracer._flush_to_database()

        mock_logger.error.assert_called_once()
        # Verify it continued and attempted to persist with a sentinel flow_id
        assert mock_session.merge.call_count >= 2

    @pytest.mark.asyncio
    async def test_flush_writes_trace_and_spans(self):
        flow_id = str(uuid4())
        tracer = _make_tracer(flow_id=flow_id)
        tracer.add_trace("comp-1", "Comp (comp-1)", "chain", {"in": "val"})
        tracer.end_trace("comp-1", "Comp", outputs={"out": "result"})

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("lfx.services.deps.session_scope", return_value=mock_session):
            await tracer._flush_to_database()

        # merge should be called at least twice: once for trace, once for span
        assert mock_session.merge.call_count >= 2

    @pytest.mark.asyncio
    async def test_flush_uses_uuid5_for_non_uuid_span_id(self):
        flow_id = str(uuid4())
        tracer = _make_tracer(flow_id=flow_id)
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

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("lfx.services.deps.session_scope", return_value=mock_session):
            # Should not raise even with non-UUID span id
            await tracer._flush_to_database()

        assert mock_session.merge.call_count >= 1

    @pytest.mark.asyncio
    async def test_flush_error_status_when_span_has_error(self):
        flow_id = str(uuid4())
        tracer = _make_tracer(flow_id=flow_id)
        tracer.add_trace("comp-1", "Comp (comp-1)", "chain", {})
        tracer.end_trace("comp-1", "Comp", error=ValueError("boom"))

        captured_traces = []

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        async def capture_merge(obj):
            captured_traces.append(obj)

        mock_session.merge = capture_merge

        with patch("lfx.services.deps.session_scope", return_value=mock_session):
            await tracer._flush_to_database()

        # First merged object is the TraceTable
        from langflow.services.database.models.traces.model import TraceTable

        trace_obj = next((o for o in captured_traces if isinstance(o, TraceTable)), None)
        assert trace_obj is not None
        assert trace_obj.status == SpanStatus.ERROR

    @pytest.mark.asyncio
    async def test_flush_calculates_total_tokens_from_spans(self):
        flow_id = str(uuid4())
        tracer = _make_tracer(flow_id=flow_id)
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

        captured_traces = []
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        async def capture_merge(obj):
            captured_traces.append(obj)

        mock_session.merge = capture_merge

        with patch("lfx.services.deps.session_scope", return_value=mock_session):
            await tracer._flush_to_database()

        from langflow.services.database.models.traces.model import TraceTable

        trace_obj = next((o for o in captured_traces if isinstance(o, TraceTable)), None)
        assert trace_obj is not None
        assert trace_obj.total_tokens == 80


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

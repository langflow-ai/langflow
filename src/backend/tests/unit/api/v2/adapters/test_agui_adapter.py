"""Tests for the ``agui`` stream adapter.

The agui adapter wraps the existing ``AGUITranslator`` and frames its
``BaseEvent`` outputs for SSE. AG-UI's wire shape is the model's
``model_dump_json(by_alias=True, exclude_none=True)``.
"""

from __future__ import annotations

import json

import pytest
from langflow.api.v2.adapters import (
    StreamAdapterContext,
    get_stream_adapter,
)


def _ctx() -> StreamAdapterContext:
    return StreamAdapterContext(run_id="run-7", thread_id="thread-7")


class TestInitialEvents:
    """The agui adapter opens the run with RUN_STARTED + STATE_SNAPSHOT."""

    def test_initial_events_emit_run_started_and_state_snapshot(self):
        adapter = get_stream_adapter("agui", _ctx())
        events = list(adapter.initial_events())
        types = [e.type for e in events]
        assert types == ["RUN_STARTED", "STATE_SNAPSHOT"]

    def test_run_started_carries_run_and_thread_ids(self):
        adapter = get_stream_adapter("agui", _ctx())
        [run_started, _snapshot] = list(adapter.initial_events())
        payload = json.loads(run_started.data_json)
        assert payload["runId"] == "run-7"
        assert payload["threadId"] == "thread-7"


class TestTranslation:
    """Each ``EventManager`` event maps to its AG-UI equivalent through the translator."""

    def test_token_emits_text_message_start_then_content(self):
        adapter = get_stream_adapter("agui", _ctx())
        events = list(adapter.translate("token", {"id": "m1", "chunk": "Hello"}))
        types = [e.type for e in events]
        assert "TEXT_MESSAGE_START" in types
        assert "TEXT_MESSAGE_CONTENT" in types

    def test_end_emits_run_finished(self):
        adapter = get_stream_adapter("agui", _ctx())
        events = list(adapter.translate("end", {}))
        assert any(e.type == "RUN_FINISHED" for e in events)

    def test_error_emits_run_error_with_message(self):
        adapter = get_stream_adapter("agui", _ctx())
        events = list(adapter.translate("error", {"error": "graph build failed"}))
        run_error = next(e for e in events if e.type == "RUN_ERROR")
        payload = json.loads(run_error.data_json)
        assert payload["message"] == "graph build failed"


class TestFinalAndErrorEvents:
    """``final_events`` is empty (RUN_FINISHED comes via translate('end'))."""

    def test_final_events_is_empty(self):
        adapter = get_stream_adapter("agui", _ctx())
        assert list(adapter.final_events()) == []


class TestErrorEventsFallback:
    """``error_events`` is the dispatcher's guaranteed fallback when ``on_error`` itself raises.

    ``_stream_event_frames`` calls ``adapter.error_events(exc)`` whenever the
    translator's own error path fails or no error event reached it. It must
    always return at least one ``RUN_ERROR`` frame carrying ``str(exc)``, for
    every exception type.
    """

    def test_error_events_returns_non_empty_sequence(self):
        adapter = get_stream_adapter("agui", _ctx())
        events = list(adapter.error_events(ValueError("bad input")))
        assert len(events) >= 1

    def test_error_events_payload_carries_str_of_exception(self):
        adapter = get_stream_adapter("agui", _ctx())
        exc = RuntimeError("graph build failed at vertex X")
        events = list(adapter.error_events(exc))
        payload = json.loads(events[0].data_json)
        assert payload["message"] == str(exc)

    @pytest.mark.parametrize(
        "exc",
        [
            ValueError("value error message"),
            RuntimeError("runtime error message"),
            Exception("base exception message"),
            KeyError("missing key"),
            TypeError("type error message"),
        ],
    )
    def test_error_events_works_for_various_exception_types(self, exc):
        """Every exception type yields exactly one RUN_ERROR carrying its str() form."""
        adapter = get_stream_adapter("agui", _ctx())
        events = list(adapter.error_events(exc))
        assert len(events) == 1
        assert events[0].type == "RUN_ERROR"
        payload = json.loads(events[0].data_json)
        # ``str(KeyError("k"))`` is ``"'k'"`` (extra quotes); compare against str(exc).
        assert payload["message"] == str(exc)

    def test_error_events_does_not_consume_translator_state(self):
        """The fallback path must work even before ``initial_events`` has been drained.

        The dispatcher can hit ``error_events`` before any translator state is
        opened; the result must still be a valid RUN_ERROR frame.
        """
        adapter = get_stream_adapter("agui", _ctx())
        events = list(adapter.error_events(RuntimeError("early failure")))
        assert len(events) == 1
        assert events[0].type == "RUN_ERROR"


class TestTerminalErrorType:
    """Buffer task watches for AG-UI RUN_ERROR to flip the job to FAILED."""

    def test_terminal_error_type_is_run_error(self):
        adapter = get_stream_adapter("agui", _ctx())
        assert adapter.terminal_error_type == "RUN_ERROR"


class TestPerInstance:
    """Each call to ``get_stream_adapter`` returns a fresh adapter (per-run state)."""

    def test_two_instances_have_independent_state(self):
        a = get_stream_adapter("agui", _ctx())
        b = get_stream_adapter("agui", StreamAdapterContext(run_id="r2", thread_id="t2"))

        # Drain initial events to advance state.
        list(a.initial_events())
        list(a.translate("token", {"id": "ma", "chunk": "x"}))
        list(b.initial_events())

        # b's translate of token "mb" should open a fresh message; a's state
        # must not leak into b. If state leaked, b would see ma as still open.
        b_events = list(b.translate("token", {"id": "mb", "chunk": "y"}))
        types_b = [e.type for e in b_events]
        # Fresh START for b's first token confirms isolated state.
        assert "TEXT_MESSAGE_START" in types_b


class TestWireFraming:
    """``data_json`` is the AG-UI camelCase wire shape via ``model_dump_json(by_alias=True)``."""

    def test_run_started_uses_camel_case_field_names(self):
        adapter = get_stream_adapter("agui", _ctx())
        [run_started, _snapshot] = list(adapter.initial_events())
        # camelCase, not snake_case
        assert "runId" in run_started.data_json
        assert "threadId" in run_started.data_json
        assert "run_id" not in run_started.data_json

    def test_data_json_excludes_none_fields(self):
        adapter = get_stream_adapter("agui", _ctx())
        events = list(adapter.translate("token", {"id": "m1", "chunk": "x"}))
        for evt in events:
            payload = json.loads(evt.data_json)
            for value in payload.values():
                assert value is not None, f"None leaked into wire: {evt.data_json}"


@pytest.mark.parametrize(
    "unknown_event_type",
    ["something_brand_new", "vertices_unknown", "telemetry"],
)
def test_unknown_event_types_yield_no_events(unknown_event_type):
    adapter = get_stream_adapter("agui", _ctx())
    events = list(adapter.translate(unknown_event_type, {}))
    assert events == []

"""Tests for the ``langflow`` stream adapter.

The langflow adapter is a passthrough: it takes Langflow EventManager events
and emits them as ``{"event": "<type>", "data": {...}}`` for SSE consumers
that already know the v1 build-flow wire shape.
"""

from __future__ import annotations

import json

import pytest
from langflow.api.v2.adapters import (
    StreamAdapterContext,
    get_stream_adapter,
)


def _ctx() -> StreamAdapterContext:
    return StreamAdapterContext(run_id="run-1", thread_id="thread-1")


class TestPassthroughShape:
    """Each translated event becomes one StreamEvent with the v1 wire shape."""

    def test_translate_emits_one_event_per_input(self):
        adapter = get_stream_adapter("langflow", _ctx())
        events = list(adapter.translate("token", {"chunk": "Hello"}))
        assert len(events) == 1

    def test_translated_data_matches_v1_build_flow_shape(self):
        adapter = get_stream_adapter("langflow", _ctx())
        [evt] = list(adapter.translate("token", {"chunk": "Hello", "id": "m1"}))
        payload = json.loads(evt.data_json)
        assert payload == {"event": "token", "data": {"chunk": "Hello", "id": "m1"}}

    def test_event_type_is_set_to_input_event_type(self):
        adapter = get_stream_adapter("langflow", _ctx())
        [evt] = list(adapter.translate("end_vertex", {"node_id": "x", "valid": True}))
        assert evt.type == "end_vertex"


class TestNoFramingFromInitialAndFinal:
    """The langflow adapter has no setup or teardown frames; SSE itself terminates the stream."""

    def test_initial_events_is_empty(self):
        adapter = get_stream_adapter("langflow", _ctx())
        assert list(adapter.initial_events()) == []

    def test_final_events_is_empty(self):
        adapter = get_stream_adapter("langflow", _ctx())
        assert list(adapter.final_events()) == []


class TestErrorHandling:
    """Errors mid-run emit a single ``error`` event and are terminal for the run."""

    def test_error_events_emit_error_payload(self):
        adapter = get_stream_adapter("langflow", _ctx())
        [evt] = list(adapter.error_events(RuntimeError("boom")))
        payload = json.loads(evt.data_json)
        assert payload == {"event": "error", "data": {"error": "boom"}}
        assert evt.type == "error"

    def test_terminal_error_type_is_error(self):
        """Used by the buffer task to decide JobStatus.FAILED."""
        adapter = get_stream_adapter("langflow", _ctx())
        assert adapter.terminal_error_type == "error"


class TestPayloadSerialization:
    """``data`` is serialized to a JSON string; non-JSON values are coerced safely."""

    def test_dict_with_nested_values_round_trips(self):
        adapter = get_stream_adapter("langflow", _ctx())
        data = {"text": "hi", "meta": {"k": [1, 2, 3]}}
        [evt] = list(adapter.translate("add_message", data))
        assert json.loads(evt.data_json) == {"event": "add_message", "data": data}

    def test_non_serializable_values_fall_back_to_str(self):
        adapter = get_stream_adapter("langflow", _ctx())

        class Custom:
            def __str__(self) -> str:
                return "<custom>"

        [evt] = list(adapter.translate("log", {"obj": Custom()}))
        payload = json.loads(evt.data_json)
        # The adapter should not raise; the custom object is stringified.
        assert payload["data"]["obj"] == "<custom>"


class TestEventTypeForwarding:
    """Every Langflow EventManager event type round-trips through the adapter."""

    @pytest.mark.parametrize(
        "event_type",
        [
            "token",
            "vertices_sorted",
            "build_start",
            "end_vertex",
            "add_message",
            "remove_message",
            "log",
            "end",
            "error",
        ],
    )
    def test_known_event_types_are_passed_through(self, event_type):
        adapter = get_stream_adapter("langflow", _ctx())
        [evt] = list(adapter.translate(event_type, {"k": "v"}))
        assert evt.type == event_type
        assert json.loads(evt.data_json)["event"] == event_type

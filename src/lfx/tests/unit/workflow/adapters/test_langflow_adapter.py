"""Tests for the ``langflow`` stream adapter.

The langflow adapter is a passthrough: it takes Langflow EventManager events
and emits them as ``{"event": "<type>", "data": {...}}`` for SSE consumers
that already know the v1 build-flow wire shape.
"""

from __future__ import annotations

import json

import pytest
from lfx.workflow.adapters import (
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

    def test_cancel_events_emit_cancelled_payload_not_error(self):
        """A user-stop is its own ``cancelled`` terminal, not ``error``, so a client can tell it from a failure."""
        adapter = get_stream_adapter("langflow", _ctx())
        [evt] = list(adapter.cancel_events("cancelled"))
        payload = json.loads(evt.data_json)
        assert payload == {"event": "cancelled", "data": {"reason": "cancelled"}}
        assert evt.type == "cancelled"

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


class TestExposeGraphState:
    """``expose_graph_state=False`` narrows the passthrough to the conversation."""

    @staticmethod
    def _narrowed() -> StreamAdapterContext:
        return StreamAdapterContext(run_id="run-1", thread_id="thread-1", expose_graph_state=False)

    _TERMINAL_VERTEX = {
        "build_data": {"id": "ChatOutput-j7k8l", "valid": True, "data": {"outputs": {"message": "hi"}}},
        "output_meta": {
            "is_terminal": True,
            "is_output": True,
            "component_id": "ChatOutput-j7k8l",
            "vertex_type": "ChatOutput",
            "display_name": "Chat Output",
        },
    }

    def test_graph_state_events_are_dropped(self):
        adapter = get_stream_adapter("langflow", self._narrowed())
        frames = list(adapter.translate("vertices_sorted", {"to_run": ["ChatInput-a1b2c"]}))
        frames += list(adapter.translate("build_start", {"id": "Agent-d3e4f"}))
        frames += list(adapter.translate("log", {"message": "internal"}))
        assert frames == []

    _DATA_SINK_VERTEX = {
        "build_data": {
            "id": "VectorStoreSearch-p9q0r",
            "valid": True,
            "data": {"outputs": {"dataframe": {"message": [{"text": "INTERNAL: margin floor is 22%"}]}}},
        },
        "output_meta": {
            # Terminal because nothing consumes it, but not an output component.
            "is_terminal": True,
            "is_output": False,
            "component_id": "VectorStoreSearch-p9q0r",
            "vertex_type": "VectorStoreSearch",
            "display_name": "Vector Store Search",
            "output_types": ["dataframe"],
        },
    }

    def test_non_output_sink_reports_nothing(self):
        """A dangling retriever is terminal without being the flow's answer.

        ``is_terminal`` is every vertex with no successors, and
        ``build_component_output`` puts a ``data``/``dataframe`` vertex's content
        in the event, so without this the narrowed stream would carry the
        component's own output and its display name.
        """
        adapter = get_stream_adapter("langflow", self._narrowed())
        assert list(adapter.translate("end_vertex", self._DATA_SINK_VERTEX)) == []

    def test_non_output_sink_still_reports_with_graph_state_on(self):
        """Sync parity is unchanged for a caller that did not opt out."""
        adapter = get_stream_adapter("langflow", _ctx())
        frames = list(adapter.translate("end_vertex", self._DATA_SINK_VERTEX))
        assert [f.type for f in frames] == ["end_vertex", "output"]

    def test_end_vertex_is_dropped_but_the_answer_survives(self):
        """The terminal ``output`` event is the flow's answer, not graph state."""
        adapter = get_stream_adapter("langflow", self._narrowed())
        frames = list(adapter.translate("end_vertex", self._TERMINAL_VERTEX))
        assert [f.type for f in frames] == ["output"]
        assert json.loads(frames[0].data_json)["data"]["component_id"] == "ChatOutput-j7k8l"

    def test_non_terminal_end_vertex_emits_nothing(self):
        """A mid-graph component has no answer to report, so nothing reaches the wire."""
        adapter = get_stream_adapter("langflow", self._narrowed())
        frames = list(
            adapter.translate(
                "end_vertex",
                {"build_data": {"id": "Store-g5h6i", "valid": True, "data": {"outputs": {"documents": "secret"}}}},
            )
        )
        assert frames == []

    def test_graph_level_build_start_and_conversation_survive(self):
        """The run-beginning marker carries no component id, so it stays."""
        adapter = get_stream_adapter("langflow", self._narrowed())
        frames = list(adapter.translate("build_start", {}))
        frames += list(adapter.translate("token", {"id": "msg-1", "chunk": "Hi"}))
        frames += list(adapter.translate("end", {}))
        assert [f.type for f in frames] == ["build_start", "token", "end"]

    def test_default_context_is_unchanged(self):
        """Without the flag the adapter passes everything through, as before."""
        adapter = get_stream_adapter("langflow", _ctx())
        frames = list(adapter.translate("end_vertex", self._TERMINAL_VERTEX))
        assert [f.type for f in frames] == ["end_vertex", "output"]

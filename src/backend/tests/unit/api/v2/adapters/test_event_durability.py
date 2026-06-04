"""Each adapter classifies frames as durable (persisted) vs ephemeral (live-only).

Milestones (run/vertex start+end, outputs, tool_call, error, STATE, run_finished)
are durable so a reattaching client can rebuild state from the durable log.
Token deltas (TEXT_MESSAGE_CONTENT / langflow ``token``) are ephemeral: high
volume, only useful live.
"""

from __future__ import annotations

from langflow.api.v2.adapters import StreamAdapterContext, get_stream_adapter


def _ctx() -> StreamAdapterContext:
    return StreamAdapterContext(run_id="run-1", thread_id="thread-1")


class TestLangflowDurability:
    def test_milestones_are_durable(self):
        adapter = get_stream_adapter("langflow", _ctx())
        for event_type in ("build_start", "end_vertex", "output", "error", "end"):
            assert adapter.is_durable(event_type) is True, event_type

    def test_token_is_ephemeral(self):
        adapter = get_stream_adapter("langflow", _ctx())
        assert adapter.is_durable("token") is False

    def test_unknown_event_defaults_to_ephemeral(self):
        adapter = get_stream_adapter("langflow", _ctx())
        assert adapter.is_durable("some_unknown_event") is False


class TestAguiDurability:
    def test_milestones_are_durable(self):
        adapter = get_stream_adapter("agui", _ctx())
        for event_type in (
            "RUN_STARTED",
            "RUN_FINISHED",
            "RUN_ERROR",
            "TEXT_MESSAGE_START",
            "TEXT_MESSAGE_END",
            "TOOL_CALL_START",
            "TOOL_CALL_END",
            "STATE_SNAPSHOT",
            "CUSTOM",
        ):
            assert adapter.is_durable(event_type) is True, event_type

    def test_token_delta_is_ephemeral(self):
        adapter = get_stream_adapter("agui", _ctx())
        assert adapter.is_durable("TEXT_MESSAGE_CONTENT") is False

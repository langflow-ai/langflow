"""HITL human_input_required translation on both stream protocols (LE-1450).

The pause is a non-terminal durable milestone: langflow passes it through and
marks it durable; agui rides the existing CUSTOM mechanism as a single
``langflow.human_input_required`` event that never closes the message or ends the run.
"""

from __future__ import annotations

import json

from lfx.workflow.adapters import StreamAdapterContext, get_stream_adapter

_PAYLOAD = {
    "request_id": "node:job-1",
    "kind": "node_input",
    "prompt": "Approve refund?",
    "options": [{"action_id": "approve", "label": "Approve"}, {"action_id": "reject", "label": "Reject"}],
    "schema": [],
    "allowed_decisions": ["approve", "reject"],
}


def _ctx() -> StreamAdapterContext:
    return StreamAdapterContext(run_id="run-1", thread_id="thread-1")


class TestLangflowHumanInputEvent:
    def test_translate_passes_through_one_frame(self):
        adapter = get_stream_adapter("langflow", _ctx())
        events = list(adapter.translate("human_input_required", _PAYLOAD))
        assert len(events) == 1
        payload = json.loads(events[0].data_json)
        assert payload == {"event": "human_input_required", "data": _PAYLOAD}

    def test_is_durable_true(self):
        adapter = get_stream_adapter("langflow", _ctx())
        assert adapter.is_durable("human_input_required") is True

    def test_not_the_terminal_error_type(self):
        adapter = get_stream_adapter("langflow", _ctx())
        assert adapter.terminal_error_type != "human_input_required"


class TestAguiHumanInputEvent:
    def test_translate_emits_single_custom_event(self):
        adapter = get_stream_adapter("agui", _ctx())
        events = list(adapter.translate("human_input_required", _PAYLOAD))
        assert len(events) == 1
        assert events[0].type == "CUSTOM"
        payload = json.loads(events[0].data_json)
        assert payload["name"] == "langflow.human_input_required"
        assert payload["value"] == _PAYLOAD

    def test_is_durable_via_custom(self):
        adapter = get_stream_adapter("agui", _ctx())
        assert adapter.is_durable("CUSTOM") is True

    def test_pause_does_not_end_the_run_or_close_the_message(self):
        adapter = get_stream_adapter("agui", _ctx())
        list(adapter.translate("token", {"id": "m1", "chunk": "Working"}))  # open a text message
        events = list(adapter.translate("human_input_required", _PAYLOAD))
        types = [e.type for e in events]
        assert "RUN_FINISHED" not in types
        assert "RUN_ERROR" not in types
        assert "TEXT_MESSAGE_END" not in types  # the open message stays open across the pause

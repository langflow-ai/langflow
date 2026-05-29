"""apply_probe_input — make an input-needing flow runnable for verification.

A built flow with an empty ChatInput cannot produce output on a probe
run. The verification loop injects a deterministic probe value so the
graph can actually execute, WITHOUT clobbering a value the user/agent
already set.
"""

from __future__ import annotations

from langflow.agentic.services.flow_probe_input import PROBE_INPUT_TEXT, apply_probe_input


def _flow(nodes):
    return {"name": "f", "data": {"nodes": nodes, "edges": []}}


def _chat_input(node_id, value=""):
    return {
        "id": node_id,
        "data": {"type": "ChatInput", "node": {"template": {"input_value": {"value": value}}}},
    }


class TestApplyProbeInput:
    def test_should_inject_probe_value_into_empty_chatinput_and_report_applied(self):
        flow = _flow([_chat_input("ChatInput-1", "")])

        applied = apply_probe_input(flow)

        assert applied is True
        val = flow["data"]["nodes"][0]["data"]["node"]["template"]["input_value"]["value"]
        assert val == PROBE_INPUT_TEXT

    def test_should_not_overwrite_a_chatinput_that_already_has_a_value(self):
        flow = _flow([_chat_input("ChatInput-1", "real user text")])

        applied = apply_probe_input(flow)

        assert applied is False
        val = flow["data"]["nodes"][0]["data"]["node"]["template"]["input_value"]["value"]
        assert val == "real user text"

    def test_should_return_false_when_flow_has_no_chatinput(self):
        flow = _flow([{"id": "Agent-1", "data": {"type": "Agent", "node": {"template": {}}}}])

        assert apply_probe_input(flow) is False

    def test_should_fill_every_empty_chatinput_when_there_are_several(self):
        flow = _flow([_chat_input("ChatInput-1", ""), _chat_input("ChatInput-2", "")])

        applied = apply_probe_input(flow)

        assert applied is True
        values = [n["data"]["node"]["template"]["input_value"]["value"] for n in flow["data"]["nodes"]]
        assert values == [PROBE_INPUT_TEXT, PROBE_INPUT_TEXT]

    def test_should_be_resilient_to_malformed_nodes(self):
        flow = _flow([{"id": "x"}, {"data": {}}, {"data": {"type": "ChatInput"}}])
        # No usable template anywhere → nothing to probe, must not raise.
        assert apply_probe_input(flow) is False

    def test_should_handle_empty_or_missing_flow_data(self):
        assert apply_probe_input({}) is False
        assert apply_probe_input({"data": {}}) is False

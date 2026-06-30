"""The v1 run endpoint cannot suspend/resume, so flows that pause for a human
(a connected Human Input node, or an agent tool gated for approval) must be
rejected up front with a clear pointer to the v2 workflows API."""

from langflow.api.v1.run_validation import flow_requires_hitl


def _node(node_id: str, node_type: str, template: dict | None = None) -> dict:
    return {
        "id": node_id,
        "data": {"id": node_id, "type": node_type, "node": {"template": template or {}}},
    }


class TestFlowRequiresHitl:
    def test_connected_human_input_requires_hitl(self):
        data = {
            "nodes": [_node("hi", "HumanInput")],
            "edges": [{"source": "hi", "target": "out"}],
        }
        assert flow_requires_hitl(data) is True

    def test_unconnected_human_input_does_not_pause(self):
        # An isolated Human Input node is skipped at runtime, so it can run on v1.
        data = {"nodes": [_node("hi", "HumanInput")], "edges": []}
        assert flow_requires_hitl(data) is False

    def test_tool_with_approval_actions_requires_hitl(self):
        template = {
            "tools_metadata": {
                "value": [{"name": "fetch_content", "approval_actions": ["approve", "reject"]}]
            }
        }
        data = {"nodes": [_node("url", "URLComponent", template)], "edges": []}
        assert flow_requires_hitl(data) is True

    def test_tool_without_approval_actions_does_not(self):
        template = {"tools_metadata": {"value": [{"name": "fetch_content", "approval_actions": []}]}}
        data = {"nodes": [_node("url", "URLComponent", template)], "edges": []}
        assert flow_requires_hitl(data) is False

    def test_plain_flow_does_not(self):
        data = {
            "nodes": [_node("chat", "ChatInput"), _node("out", "ChatOutput")],
            "edges": [{"source": "chat", "target": "out"}],
        }
        assert flow_requires_hitl(data) is False

    def test_missing_keys_are_safe(self):
        assert flow_requires_hitl({}) is False

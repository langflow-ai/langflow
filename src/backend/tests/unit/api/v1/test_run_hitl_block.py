"""Guard tests for blocking HITL flows on the synchronous v1 run endpoint.

The v1 run endpoint cannot suspend/resume, so flows that pause for a human
(a connected Human Input node, or an agent tool gated for approval) must be
rejected up front with a clear pointer to the v2 workflows API.
"""

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
        template = {"tools_metadata": {"value": [{"name": "fetch_content", "approval_actions": ["approve", "reject"]}]}}
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


def _group(group_id: str, nodes: list[dict], edges: list[dict]) -> dict:
    return {
        "id": group_id,
        "data": {
            "id": group_id,
            "type": "GroupNode",
            "node": {"template": {}, "flow": {"data": {"nodes": nodes, "edges": edges}}},
        },
    }


class TestFlowRequiresHitlInGroups:
    """The graph flattens group nodes before running, so the guard must see grouped HITL nodes."""

    def test_human_input_inside_a_group_requires_hitl(self):
        group = _group(
            "g", [_node("hi", "HumanInput"), _node("save", "SaveToFile")], [{"source": "hi", "target": "save"}]
        )
        assert flow_requires_hitl({"nodes": [_node("chat", "ChatInput"), group], "edges": []}) is True

    def test_human_input_inside_a_nested_group_requires_hitl(self):
        inner = _group(
            "inner", [_node("hi", "HumanInput"), _node("save", "SaveToFile")], [{"source": "hi", "target": "save"}]
        )
        outer = _group("outer", [inner], [])
        assert flow_requires_hitl({"nodes": [outer], "edges": []}) is True

    def test_approval_gated_tool_inside_a_group_requires_hitl(self):
        template = {"tools_metadata": {"value": [{"name": "fetch_content", "approval_actions": ["approve"]}]}}
        group = _group("g", [_node("url", "URLComponent", template)], [])
        assert flow_requires_hitl({"nodes": [group], "edges": []}) is True

    def test_isolated_human_input_inside_a_group_does_not(self):
        group = _group("g", [_node("hi", "HumanInput")], [])
        assert flow_requires_hitl({"nodes": [group], "edges": []}) is False

    def test_malformed_group_does_not_raise(self):
        broken = {
            "id": "g",
            "data": {"id": "g", "type": "GroupNode", "node": {"template": {}, "flow": {"data": {"edges": []}}}},
        }
        assert flow_requires_hitl({"nodes": [broken], "edges": []}) is False

    def test_grouped_human_input_is_still_found_when_another_group_cannot_be_flattened(self):
        wired = _group(
            "a", [_node("hi", "HumanInput"), _node("save", "SaveToFile")], [{"source": "hi", "target": "save"}]
        )
        broken = {
            "id": "b",
            "data": {"id": "b", "type": "GroupNode", "node": {"template": {}, "flow": {"data": {"edges": []}}}},
        }
        assert flow_requires_hitl({"nodes": [wired, broken], "edges": []}) is True

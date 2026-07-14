"""Structural checks for the Delegation Planner starter project."""

import json
from pathlib import Path


TEMPLATE_PATH = (
    Path(__file__).parent.parent
    / "base"
    / "langflow"
    / "initial_setup"
    / "starter_projects"
    / "Delegation Planner.json"
)


def load_template() -> dict:
    return json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))


def test_delegation_planner_has_minimal_review_flow():
    template = load_template()
    nodes = template["data"]["nodes"]
    edges = template["data"]["edges"]

    assert template["name"] == "Delegation Planner"
    assert template["tags"] == ["assistants", "agents"]
    assert len(nodes) == 5
    assert len(edges) == 3

    node_types = [node["data"]["type"] for node in nodes]
    assert sorted(node_types) == ["Agent", "Agent", "ChatInput", "ChatOutput", "note"]

    connections = {(edge["source"], edge["target"]) for edge in edges}
    assert connections == {
        ("ChatInput-NuUHZ", "Agent-b7nmW"),
        ("Agent-b7nmW", "Agent-EQcU8"),
        ("Agent-EQcU8", "ChatOutput-GWGKe"),
    }


def test_delegation_planner_keeps_plain_language_boundaries():
    template = load_template()
    nodes = {node["id"]: node for node in template["data"]["nodes"]}
    planner = nodes["Agent-b7nmW"]["data"]["node"]["template"]
    reviewer = nodes["Agent-EQcU8"]["data"]["node"]["template"]
    note = nodes["note-seq"]["data"]["node"]["description"]

    assert "Do not perform the task" in planner["system_prompt"]["value"]
    assert "Check with me first" in planner["system_prompt"]["value"]
    assert "Evidence to bring back" in planner["system_prompt"]["value"]
    assert "Do not perform the underlying task" in reviewer["system_prompt"]["value"]
    assert "planning assistance, not a safety guarantee" in reviewer["system_prompt"]["value"]
    assert "This flow plans work" in note

    for agent in (planner, reviewer):
        assert agent["add_calculator_tool"]["value"] is False
        assert agent["add_current_date_tool"]["value"] is False
        assert agent["tools"]["value"] == ""

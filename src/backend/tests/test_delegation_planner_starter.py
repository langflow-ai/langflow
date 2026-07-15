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
    """Load the Delegation Planner starter project as parsed JSON."""
    return json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))


def test_delegation_planner_has_minimal_review_flow():
    """Verify the starter keeps its five-node planning and review topology."""
    template = load_template()
    nodes = template["data"]["nodes"]
    edges = template["data"]["edges"]

    assert template["name"] == "Delegation Planner"
    assert template["tags"] == ["assistants", "agents"]
    assert len(nodes) == 5
    assert len(edges) == 3

    node_types = [node["data"]["type"] for node in nodes]
    assert sorted(node_types) == ["Agent", "Agent", "ChatInput", "ChatOutput", "note"]

    node_types_by_id = {node["id"]: node["data"]["type"] for node in nodes}
    connection_types = {(node_types_by_id[edge["source"]], node_types_by_id[edge["target"]]) for edge in edges}
    assert connection_types == {
        ("ChatInput", "Agent"),
        ("Agent", "Agent"),
        ("Agent", "ChatOutput"),
    }


def test_delegation_planner_keeps_plain_language_boundaries():
    """Verify the starter exposes accurate labels and safe planning boundaries."""
    template = load_template()
    nodes = template["data"]["nodes"]
    agents = [node["data"] for node in nodes if node["data"]["type"] == "Agent"]
    planner_data = next(
        agent for agent in agents if "Do not perform the task" in agent["node"]["template"]["system_prompt"]["value"]
    )
    reviewer_data = next(
        agent
        for agent in agents
        if "planning assistance, not a safety guarantee" in agent["node"]["template"]["system_prompt"]["value"]
    )
    planner = planner_data["node"]["template"]
    reviewer = reviewer_data["node"]["template"]
    note = next(node["data"]["node"]["description"] for node in nodes if node["data"]["type"] == "note")

    assert planner_data["display_name"] == "Delegation Planner"
    assert "without performing the task" in planner_data["description"]
    assert reviewer_data["display_name"] == "Boundary Reviewer"
    assert "tighten its boundaries" in reviewer_data["description"]
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

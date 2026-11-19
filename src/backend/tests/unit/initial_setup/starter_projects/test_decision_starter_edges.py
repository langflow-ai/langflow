"""Every decision starter's edges match the fields they connect, so the editor keeps them on load."""

import json
from pathlib import Path

import pytest

STARTERS = Path(__file__).resolve().parents[4] / "base/langflow/initial_setup/starter_projects"


@pytest.mark.parametrize("name", ["Message Classifier", "Support Ticket Routing", "LLM Gatekeeper"])
def test_edge_handles_match_the_fields_they_connect(name):
    """The editor drops any edge whose handle disagrees with its field, as cleanEdges does on load."""
    data = json.loads((STARTERS / f"{name}.json").read_text(encoding="utf-8"))["data"]
    nodes = {node["id"]: node["data"]["node"] for node in data["nodes"]}
    assert data["edges"]
    for edge in data["edges"]:
        source, target = edge["data"]["sourceHandle"], edge["data"]["targetHandle"]
        assert json.loads(edge["sourceHandle"].replace("œ", '"')) == source
        assert json.loads(edge["targetHandle"].replace("œ", '"')) == target
        output = next(output for output in nodes[edge["source"]]["outputs"] if output["name"] == source["name"])
        assert source["output_types"] == output["types"]
        field = nodes[edge["target"]]["template"][target["fieldName"]]
        assert (target["type"], target["inputTypes"]) == (field["type"], field["input_types"])

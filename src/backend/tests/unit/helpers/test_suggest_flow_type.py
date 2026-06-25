"""Tests for helpers.flow.suggest_flow_type (F1 agent auto-detect)."""

from __future__ import annotations

import json
from pathlib import Path

import langflow
import pytest
from langflow.helpers.flow import suggest_flow_type
from langflow.services.database.models.flow.model import FlowType

_STARTERS = Path(langflow.__file__).parent / "initial_setup" / "starter_projects"


def _load_agent_starter() -> dict:
    """Return the graph data of a real starter project that contains an Agent node."""
    for path in sorted(_STARTERS.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8")).get("data") or {}
        if any((node.get("data") or {}).get("type") == "Agent" for node in data.get("nodes") or []):
            return data
    pytest.skip("No starter project with an Agent node found")
    return {}


def _first_non_agent_node(graph_data: dict) -> dict:
    for node in graph_data.get("nodes") or []:
        node_data = node.get("data") or {}
        if node_data.get("type") != "Agent" and node_data.get("node", {}).get("template", {}).get("code", {}).get(
            "value"
        ):
            return node
    pytest.skip("No non-agent node with code found in starter")
    return {}


def test_suggest_agent_for_flow_with_agent_component():
    agent_graph = _load_agent_starter()
    assert suggest_flow_type(agent_graph) == FlowType.AGENT


def test_suggest_workflow_for_flow_without_agent_component():
    agent_graph = _load_agent_starter()
    workflow_graph = {"nodes": [_first_non_agent_node(agent_graph)], "edges": []}
    assert suggest_flow_type(workflow_graph) == FlowType.WORKFLOW


def test_suggest_workflow_for_empty_or_missing_data():
    assert suggest_flow_type({"nodes": [], "edges": []}) == FlowType.WORKFLOW
    assert suggest_flow_type(None) == FlowType.WORKFLOW


def test_suggest_never_raises_on_malformed_nodes():
    bad = {"nodes": [{"data": {"node": {"template": {"code": {"value": "this is not python ("}}}}}]}
    assert suggest_flow_type(bad) == FlowType.WORKFLOW

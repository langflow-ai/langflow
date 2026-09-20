"""Regression guard: shipped starter projects must advertise their inputs over MCP.

A project's flows are published on its MCP server, and the very first flow a new user creates comes
from this template picker. ``api_editable`` — the Inspector's per-field "API" toggle — defaults to
False, is written only by the frontend, and has no backfill, so gating the advertised schema on it
without a per-flow fallback publishes every one of these templates with an input schema containing
nothing but the optional ``session_id``. The failure is silent at both ends: the tool call returns
``isError: false`` with empty content and the flow runs on an empty message.

These tests are file-system level on purpose: they read the shipped JSON the same way the seeder
does at first boot, then run the real ``tools/list`` schema derivation over it.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from langflow.helpers.flow import json_schema_from_flow
from lfx.graph.schema import INPUT_COMPONENTS

STARTER_PROJECTS_DIR = Path(__file__).resolve().parents[3] / "base" / "langflow" / "initial_setup" / "starter_projects"


def _starter_project_files() -> list[Path]:
    if not STARTER_PROJECTS_DIR.is_dir():
        msg = f"starter_projects directory not found at {STARTER_PROJECTS_DIR}"
        raise FileNotFoundError(msg)
    return sorted(STARTER_PROJECTS_DIR.glob("*.json"))


def _input_node_types(flow_data: dict) -> list[str]:
    return [
        node.get("data", {}).get("type")
        for node in flow_data.get("nodes", [])
        if node.get("data", {}).get("type") in INPUT_COMPONENTS
    ]


@pytest.mark.parametrize("starter_path", _starter_project_files(), ids=lambda path: path.stem)
def test_starter_project_advertises_its_flow_inputs_over_mcp(starter_path: Path):
    """A shipped template with an input node must advertise more than the injected session_id."""
    flow_data = json.loads(starter_path.read_text(encoding="utf-8")).get("data") or {}
    input_types = _input_node_types(flow_data)
    if not input_types:
        pytest.skip(f"{starter_path.stem} has no input component; MCP has nothing to advertise")

    schema = json_schema_from_flow(SimpleNamespace(data=flow_data))
    advertised = set(schema["properties"]) - {"session_id"}

    assert advertised, (
        f"{starter_path.stem} publishes an MCP tool whose only input is the optional session_id. "
        f"A caller obeying that schema runs the flow with no message."
    )
    if "ChatInput" in input_types:
        assert "input_value" in advertised, (
            f"{starter_path.stem} accepts input_value at call time but does not advertise it."
        )

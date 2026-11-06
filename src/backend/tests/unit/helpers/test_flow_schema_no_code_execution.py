"""Deriving a flow's input schema must never execute the flow's stored component source.

The schema is published to callers who could not build the flow themselves: MCP ``tools/list``
on a project shared with ``auth_type="none"`` runs for anonymous clients, and the A2A agent card
is public by spec. The public *call* paths refuse flows carrying executable custom code, so any
listing path that evaluates that code hands an anonymous caller the execution the call path
withholds.

A node's stored ``code`` is evaluated whenever its component is instantiated, and module-level
assignments run as part of that evaluation. Every node in these flows carries an assignment whose
right-hand side writes a marker file, so the marker exists only if something executed stored code.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import langflow
import pytest
from langflow.api.v1 import mcp_utils
from langflow.helpers.flow import get_flow_input_tweaks, json_schema_from_flow
from lfx.graph.graph.base import Graph

_STARTERS = Path(langflow.__file__).parent / "initial_setup" / "starter_projects"


def _plant_module_level_side_effect(flow_data: dict, marker: Path) -> dict:
    """Return a copy of ``flow_data`` whose every stored component source writes ``marker`` on load."""
    planted = copy.deepcopy(flow_data)
    payload = f"_SCHEMA_PROBE = __import__('pathlib').Path({str(marker)!r}).write_text('executed')\n"
    for node in planted["nodes"]:
        code_field = node.get("data", {}).get("node", {}).get("template", {}).get("code")
        if isinstance(code_field, dict) and isinstance(code_field.get("value"), str):
            code_field["value"] = payload + code_field["value"]
    return planted


@pytest.fixture
def marker(tmp_path: Path) -> Path:
    return tmp_path / "stored-code-executed"


@pytest.fixture
def planted_flow_data(marker: Path) -> dict:
    flow_data = json.loads((_STARTERS / "Basic Prompting.json").read_text(encoding="utf-8"))["data"]
    return _plant_module_level_side_effect(flow_data, marker)


def test_planted_payload_runs_when_components_are_instantiated(planted_flow_data, marker):
    """Control: a full build does run the planted source, so the assertions below are not vacuous."""
    Graph.from_payload(copy.deepcopy(planted_flow_data))

    assert marker.exists()


def test_json_schema_from_flow_does_not_execute_stored_code(planted_flow_data, marker):
    schema = json_schema_from_flow(SimpleNamespace(data=planted_flow_data))

    assert not marker.exists()
    # Schema derivation still reads the stored template: the chat input stays advertised.
    assert "input_value" in schema["properties"]


def test_json_schema_from_flow_without_allowlist_does_not_execute_stored_code(planted_flow_data, marker):
    """The A2A agent card derives its schema with ``require_api_editable=False``."""
    schema = json_schema_from_flow(SimpleNamespace(data=planted_flow_data), require_api_editable=False)

    assert not marker.exists()
    assert "input_value" in schema["properties"]


def test_get_flow_input_tweaks_does_not_execute_stored_code(planted_flow_data, marker):
    tweaks = get_flow_input_tweaks(SimpleNamespace(data=planted_flow_data), {"input_value": "hi"})

    assert not marker.exists()
    assert list(tweaks.values()) == [{"input_value": "hi"}]


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


class _FakeSession:
    def __init__(self, flows):
        self._flows = flows

    async def exec(self, _stmt):
        return _FakeResult(self._flows)


class _FakeSessionContext:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.asyncio
async def test_anonymous_project_tools_list_does_not_execute_stored_code(monkeypatch, planted_flow_data, marker):
    """``tools/list`` on an ``auth_type="none"`` project runs as the owner with no authenticated caller."""
    project_id = uuid4()
    owner_id = uuid4()
    flow = SimpleNamespace(
        id=uuid4(),
        name="planted_flow",
        user_id=owner_id,
        folder_id=project_id,
        action_name="planted_flow",
        action_description=None,
        description=None,
        mcp_enabled=True,
        data=planted_flow_data,
    )
    monkeypatch.setattr(mcp_utils, "session_scope", lambda: _FakeSessionContext(_FakeSession([flow])))

    user_token = mcp_utils.current_user_ctx.set(SimpleNamespace(id=owner_id))
    caller_token = mcp_utils.authenticated_caller_ctx.set(None)
    try:
        result = await mcp_utils.handle_list_tools_result(project_id=project_id, mcp_enabled_only=True)
    finally:
        mcp_utils.authenticated_caller_ctx.reset(caller_token)
        mcp_utils.current_user_ctx.reset(user_token)

    assert not marker.exists()
    assert [tool.name for tool in result.tools] == ["planted_flow"]
    assert "input_value" in result.tools[0].inputSchema["properties"]

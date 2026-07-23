"""Tests for the agentic MCP server's authenticated-user binding.

The flow/component tools must derive the acting user from the server-injected
``LANGFLOW_AGENTIC_USER_ID`` env var (set by Langflow at spawn from the request identity), NOT
from a caller-supplied parameter. ``_bound_user_id`` fails closed when the env var is absent so a
server spawned without a bound identity cannot read or write any user's flows.
"""

import inspect

import pytest
from langflow.agentic.mcp import server as mcp_server
from lfx.base.mcp.security import AGENTIC_USER_ID_ENV_VAR


def test_bound_user_id_returns_env_value(monkeypatch):
    monkeypatch.setenv(AGENTIC_USER_ID_ENV_VAR, "11111111-1111-1111-1111-111111111111")
    assert mcp_server._bound_user_id() == "11111111-1111-1111-1111-111111111111"


def test_bound_user_id_fails_closed_when_unset(monkeypatch):
    monkeypatch.delenv(AGENTIC_USER_ID_ENV_VAR, raising=False)
    with pytest.raises(ValueError, match="not bound to an authenticated user"):
        mcp_server._bound_user_id()


def test_bound_user_id_fails_closed_when_empty(monkeypatch):
    monkeypatch.setenv(AGENTIC_USER_ID_ENV_VAR, "")
    with pytest.raises(ValueError, match="not bound to an authenticated user"):
        mcp_server._bound_user_id()


@pytest.mark.parametrize(
    "tool",
    [
        mcp_server.create_flow_from_template,
        mcp_server.visualize_flow_graph,
        mcp_server.get_flow_ascii_diagram,
        mcp_server.get_flow_text_representation,
        mcp_server.get_flow_structure_summary,
        mcp_server.get_flow_component_details,
        mcp_server.get_flow_component_field_value,
        mcp_server.update_flow_component_field,
        mcp_server.list_flow_component_fields,
        mcp_server.run_assistant,
    ],
)
def test_mcp_flow_tools_do_not_accept_caller_supplied_user_id(tool):
    assert "user_id" not in inspect.signature(tool).parameters

"""Tests for the agentic MCP server's authenticated-user binding.

The flow/component tools must derive the acting user from the server-injected
``LANGFLOW_AGENTIC_USER_ID`` env var (set by Langflow at spawn from the request identity), NOT
from a caller-supplied parameter. ``_bound_user_id`` fails closed when the env var is absent so a
server spawned without a bound identity cannot read or write any user's flows.
"""

import inspect
from unittest.mock import AsyncMock

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


async def test_standalone_service_boot_starts_provider_policy_refresh(monkeypatch):
    from langflow.services import utils as service_utils
    from langflow.services.task import model_provider_policy_refresh as refresh_module

    events = []

    async def initialize_services():
        events.append("initialize")

    async def start_refresh():
        events.append("start_refresh")

    monkeypatch.setattr(mcp_server, "_services_initialized", False)
    monkeypatch.setattr(mcp_server, "_policy_refresh_started", False)
    monkeypatch.setattr(mcp_server, "get_db_service", lambda: object())
    monkeypatch.setattr(service_utils, "initialize_services", initialize_services)
    monkeypatch.setattr(
        refresh_module.model_provider_policy_refresh_worker,
        "start",
        AsyncMock(side_effect=start_refresh),
    )

    await mcp_server._ensure_services()

    assert events == ["initialize", "start_refresh"]
    assert mcp_server._services_initialized is True
    assert mcp_server._policy_refresh_started is True


async def test_refresh_start_failure_retries_without_reinitializing_services(monkeypatch):
    from langflow.services import utils as service_utils
    from langflow.services.task import model_provider_policy_refresh as refresh_module

    initialize_services = AsyncMock()
    start_refresh = AsyncMock(side_effect=[RuntimeError("refresh start failed"), None])
    monkeypatch.setattr(mcp_server, "_services_initialized", False)
    monkeypatch.setattr(mcp_server, "_policy_refresh_started", False)
    monkeypatch.setattr(mcp_server, "get_db_service", lambda: object())
    monkeypatch.setattr(service_utils, "initialize_services", initialize_services)
    monkeypatch.setattr(refresh_module.model_provider_policy_refresh_worker, "start", start_refresh)

    with pytest.raises(RuntimeError, match="refresh start failed"):
        await mcp_server._ensure_services()

    assert mcp_server._services_initialized is True
    assert mcp_server._policy_refresh_started is False

    await mcp_server._ensure_services()

    initialize_services.assert_awaited_once_with()
    assert start_refresh.await_count == 2
    assert mcp_server._policy_refresh_started is True


async def test_mcp_lifespan_stops_started_policy_refresh(monkeypatch):
    from langflow.services.task import model_provider_policy_refresh as refresh_module

    stop_refresh = AsyncMock()
    monkeypatch.setattr(mcp_server, "_policy_refresh_started", True)
    monkeypatch.setattr(refresh_module.model_provider_policy_refresh_worker, "stop", stop_refresh)

    async with mcp_server._service_lifespan(mcp_server.mcp):
        pass

    stop_refresh.assert_awaited_once_with()
    assert mcp_server._policy_refresh_started is False


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

import pytest
from lfx.components.models_and_agents.mcp_component import MCPToolsComponent


def test_normalize_tool_execution_timeout_returns_none_for_zero():
    component = MCPToolsComponent()

    component.tool_execution_timeout = 0.0

    assert component._normalize_tool_execution_timeout() is None


def test_normalize_tool_execution_timeout_returns_float_for_positive_value():
    component = MCPToolsComponent()

    component.tool_execution_timeout = 12

    assert component._normalize_tool_execution_timeout() == 12.0


def test_normalize_tool_execution_timeout_rejects_negative_value_with_field_specific_message():
    component = MCPToolsComponent()

    component.tool_execution_timeout = -1

    with pytest.raises(ValueError, match=r"Tool Execution Timeout must be greater than or equal to 0\."):
        component._normalize_tool_execution_timeout()


def test_mcp_servers_cache_key_rejects_negative_timeout_with_field_specific_message():
    component = MCPToolsComponent()
    component.tool_execution_timeout = -1

    with pytest.raises(ValueError, match=r"Tool Execution Timeout must be greater than or equal to 0\."):
        component._mcp_servers_cache_key("demo-server")


def test_apply_tool_execution_timeout_to_clients_updates_both_clients():
    component = MCPToolsComponent()

    component._apply_tool_execution_timeout_to_clients(12.5)

    assert component.stdio_client._tool_execution_timeout == 12.5
    assert component.streamable_http_client._tool_execution_timeout == 12.5

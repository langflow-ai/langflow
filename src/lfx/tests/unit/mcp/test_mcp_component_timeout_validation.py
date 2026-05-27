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


def test_mcp_servers_cache_key_clamps_negative_timeout_to_zero():
    component = MCPToolsComponent()
    component.tool_execution_timeout = -1

    cache_key = component._mcp_servers_cache_key("demo-server")
    assert "demo-server" in cache_key


@pytest.mark.asyncio
async def test_update_build_config_resets_negative_timeout():
    component = MCPToolsComponent()
    build_config = {"tool_execution_timeout": {"value": -1, "placeholder": ""}}

    result = await component.update_build_config(build_config, "-1", "tool_execution_timeout")

    assert result["tool_execution_timeout"]["value"] == 0.0
    assert "Negative timeouts cause immediate failures" in result["tool_execution_timeout"]["placeholder"]


@pytest.mark.asyncio
async def test_update_build_config_handles_empty_timeout_safely():
    component = MCPToolsComponent()
    build_config = {"tool_execution_timeout": {"value": "", "placeholder": ""}}

    # Should not crash and should clear any placeholder
    result = await component.update_build_config(build_config, "", "tool_execution_timeout")

    assert result["tool_execution_timeout"]["placeholder"] == ""
    assert result["tool_execution_timeout"]["value"] == ""

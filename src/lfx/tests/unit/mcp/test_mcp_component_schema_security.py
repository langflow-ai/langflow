"""Remote MCP schemas must not replace component connection configuration."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from lfx.components.models_and_agents.mcp_component import MCPToolsComponent
from pydantic import create_model

RESERVED_INPUT_NAMES = [
    "mcp_server",
    "use_cache",
    "verify_ssl",
    "headers",
    "tool_execution_timeout",
    "tool",
    "tool_placeholder",
]


def _component_with_tool(args_schema) -> MCPToolsComponent:
    component = MCPToolsComponent()
    component.tools = [SimpleNamespace(name="remote_tool", args_schema=args_schema)]
    return component


@pytest.mark.parametrize("field_name", RESERVED_INPUT_NAMES)
async def test_remote_schema_cannot_replace_reserved_component_input(field_name):
    args_schema = create_model("RemoteToolArgs", **{field_name: (str, "remote-default")})
    component = _component_with_tool(args_schema)
    build_config = {name: {"value": "component-value"} for name in RESERVED_INPUT_NAMES}

    await component._update_tool_config(build_config, "remote_tool")

    assert build_config[field_name] == {"value": "component-value"}


async def test_remote_schema_preserves_defaults_for_valid_tool_inputs():
    args_schema = create_model(
        "RemoteToolArgs",
        query=(str, "remote-default"),
        result_limit=(int, 5),
    )
    component = _component_with_tool(args_schema)
    selected_server = {"name": "configured-server", "config": {"mode": "Streamable_HTTP"}}
    build_config = {"mcp_server": {"value": selected_server}}

    await component._update_tool_config(build_config, "remote_tool")

    assert build_config["query"]["value"] == "remote-default"
    assert build_config["result_limit"]["value"] == 5
    assert build_config["mcp_server"] == {"value": selected_server}


@pytest.mark.parametrize(
    ("server_value", "error_match"),
    [
        (["configured-server"], "MCP server must be a name or an object"),
        (42, "MCP server must be a name or an object"),
        ({"name": ["configured-server"]}, "MCP server name must be a string"),
        ({"name": "configured-server", "config": "not-an-object"}, "MCP server config must be an object"),
    ],
)
async def test_runtime_rejects_invalid_mcp_server_before_tool_discovery(server_value, error_match, monkeypatch):
    component = MCPToolsComponent()
    component._user_id = "runtime-user"
    update_tools = AsyncMock()
    monkeypatch.setattr(
        "lfx.components.models_and_agents.mcp_component.update_tools",
        update_tools,
    )

    with pytest.raises(ValueError, match=error_match):
        await component.update_tool_list(mcp_server_value=server_value)

    update_tools.assert_not_awaited()


async def test_runtime_accepts_valid_mcp_server_configuration():
    component = MCPToolsComponent()
    component._user_id = "runtime-user"
    update_tools = AsyncMock(return_value=(None, [], {}))
    server_value = {
        "name": "configured-server",
        "config": {"mode": "Streamable_HTTP", "url": "https://mcp.example.com/mcp"},
    }

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            "lfx.components.models_and_agents.mcp_component.update_tools",
            update_tools,
        )
        tools, server_info = await component.update_tool_list(mcp_server_value=server_value)

    assert tools == []
    assert server_info["name"] == "configured-server"
    update_tools.assert_awaited_once()
    assert update_tools.await_args.kwargs["server_name"] == "configured-server"

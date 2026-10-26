"""Remote MCP schemas must not replace component connection configuration."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from lfx.components.models_and_agents.mcp_component import MCPToolsComponent
from pydantic import create_model

RESERVED_INPUT_NAMES = dict.fromkeys([*MCPToolsComponent.default_keys, "tools_metadata"])
INVALID_SERVER_VALUES = [
    (["configured-server"], "MCP server must be a name or an object"),
    (42, "MCP server must be a name or an object"),
    ({"name": ["configured-server"]}, "MCP server name must be a string"),
    ({"name": "configured-server", "config": "not-an-object"}, "MCP server config must be an object"),
]


def _component_with_tool(args_schema) -> MCPToolsComponent:
    component = MCPToolsComponent()
    component.tools = [SimpleNamespace(name="remote_tool", args_schema=args_schema)]
    return component


def _args_schema_with_field(field_name):
    model_field = create_model("RemoteToolArgs", value=(str, "remote-default")).model_fields["value"]
    return SimpleNamespace(model_fields={field_name: model_field})


@pytest.mark.parametrize("field_name", RESERVED_INPUT_NAMES)
async def test_remote_schema_cannot_replace_reserved_component_input(field_name):
    component = _component_with_tool(_args_schema_with_field(field_name))
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
    tools_metadata = {"show": True}
    build_config = {"mcp_server": {"value": selected_server}, "tools_metadata": tools_metadata}

    await component._update_tool_config(build_config, "remote_tool")

    assert build_config["query"]["value"] == "remote-default"
    assert build_config["result_limit"]["value"] == 5
    assert build_config["mcp_server"] == {"value": selected_server}
    assert build_config["tools_metadata"] is tools_metadata


@pytest.mark.parametrize("field_name", RESERVED_INPUT_NAMES)
def test_reserved_tool_argument_is_rejected_before_kwargs_are_built(field_name):
    component = MCPToolsComponent()
    component._attributes[field_name] = "component-value"

    with pytest.raises(ValueError, match="reserved component field"):
        component._build_tool_kwargs(_args_schema_with_field(field_name))


async def test_colliding_tool_cannot_execute():
    exec_tool = SimpleNamespace(args_schema=_args_schema_with_field("mcp_server"), coroutine=AsyncMock())
    component = MCPToolsComponent()
    component.tool = "remote_tool"
    component._tool_cache = {"remote_tool": exec_tool}
    component.set_attributes({"mcp_server": {"name": "configured-server"}})
    component.update_tool_list = AsyncMock(return_value=([exec_tool], {}))

    with pytest.raises(ValueError, match="reserved component field"):
        await component.build_output()

    exec_tool.coroutine.assert_not_awaited()


@pytest.mark.parametrize(("server_value", "error_match"), INVALID_SERVER_VALUES)
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


@pytest.mark.parametrize(("server_value", "error_match"), INVALID_SERVER_VALUES)
async def test_get_tools_rejects_invalid_mcp_server_before_cache_access(server_value, error_match):
    component = MCPToolsComponent()
    component.mcp_server = server_value
    component.update_tool_list = AsyncMock()

    with pytest.raises(ValueError, match=error_match):
        await component._get_tools()

    component.update_tool_list.assert_not_awaited()


@pytest.mark.parametrize(("server_value", "error_match"), INVALID_SERVER_VALUES)
async def test_update_build_config_rejects_invalid_mcp_server_before_cache_access(server_value, error_match):
    component = MCPToolsComponent()
    component.use_cache = True
    component._user_id = "runtime-user"
    component.update_tool_list = AsyncMock()
    build_config = {
        "mcp_server": {"value": {"name": "configured-server"}},
        "tool": {"show": True, "options": [], "value": "", "placeholder": ""},
        "tool_placeholder": {"tool_mode": True},
        "tools_metadata": {"show": False},
        "use_cache": {"value": True},
        "verify_ssl": {"value": True},
        "headers": {"value": []},
    }

    with pytest.raises(ValueError, match=error_match):
        await component.update_build_config(build_config, server_value, "mcp_server")

    component.update_tool_list.assert_not_awaited()


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

"""Unit tests for ``ConfluentContextEngineComponent`` (``lfx-confluent``).

The MCP engine (``lfx.base.mcp.util.update_tools``) is patched at the preset
base module so no network access is needed; the tests assert endpoint
templating, header construction, Tool-Mode wiring, and the direct-run path.
"""

from __future__ import annotations

import base64
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from lfx.utils.ssrf_protection import SSRFProtectionError
from lfx_confluent import ConfluentContextEngineComponent
from lfx_confluent.components.confluent.context_engine import CONTEXT_ENGINE_TOOLS

UPDATE_TOOLS_TARGET = "lfx.base.mcp.preset.update_tools"


def _tool(name: str, result=None):
    async def coroutine(**kwargs):
        if result is not None:
            return result
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=json.dumps({"echo": kwargs}))])

    return SimpleNamespace(name=name, description=f"{name} tool", coroutine=coroutine)


def _engine(tools):
    return AsyncMock(return_value=("Streamable_HTTP", tools, {t.name: t for t in tools}))


@pytest.fixture
def component() -> ConfluentContextEngineComponent:
    c = ConfluentContextEngineComponent()
    c.region = "us-east-1"
    c.organization_id = "org-1"
    c.environment_id = "env-abc"
    c.kafka_cluster_id = "lkc-xyz"
    c.api_key = "key"  # pragma: allowlist secret
    c.api_secret = "secret"  # noqa: S105  # pragma: allowlist secret
    c.endpoint_override = ""
    c.cloud = "aws"
    c.tool = ""
    c.tool_arguments = "{}"
    c.tool_execution_timeout = 0.0
    c.verify_ssl = True
    return c


def test_component_metadata():
    """Class name / component name are permanent identifiers for saved flows."""
    assert ConfluentContextEngineComponent.__name__ == "ConfluentContextEngineComponent"
    assert ConfluentContextEngineComponent.name == "ConfluentContextEngine"
    assert ConfluentContextEngineComponent.add_tool_output is True


def test_tool_dropdown_seeded_with_documented_tools():
    tool_input = next(i for i in ConfluentContextEngineComponent.inputs if i.name == "tool")
    assert tool_input.options == CONTEXT_ENGINE_TOOLS


def test_hidden_tool_mode_trigger_present():
    trigger = next(i for i in ConfluentContextEngineComponent.inputs if i.name == "tool_mode_trigger")
    assert trigger.tool_mode is True
    assert trigger.show is False


def test_endpoint_url_templated_from_ids(component):
    assert component.endpoint_url() == (
        "https://mcp.us-east-1.aws.confluent.cloud/mcp/v1/context-engine/"
        "organizations/org-1/environments/env-abc/kafka-clusters/lkc-xyz"
    )


def test_endpoint_override_wins_and_is_ssrf_checked(component):
    component.endpoint_override = "https://mcp.example.com/mcp/v1/context-engine/x"
    assert component.endpoint_url() == "https://mcp.example.com/mcp/v1/context-engine/x"
    component.endpoint_override = "http://169.254.169.254/latest/meta-data"
    with pytest.raises(SSRFProtectionError):
        component.endpoint_url()


def test_mcp_server_config_has_basic_auth_header(component):
    name, config = component._mcp_server_config()
    assert name == "confluent-context-engine-lkc-xyz"
    assert config["mode"] == "Streamable_HTTP"
    assert config["verify_ssl"] is True
    token = config["headers"]["Authorization"].removeprefix("Basic ")
    assert base64.b64decode(token).decode() == "key:secret"


async def test_get_tools_returns_engine_tools(component):
    tools = [_tool("list_topics"), _tool("query_data")]
    with patch(UPDATE_TOOLS_TARGET, new=_engine(tools)) as upd:
        got = await component._get_tools()
    assert [t.name for t in got] == ["list_topics", "query_data"]
    server_name, server_config = upd.await_args.args[:2]
    assert server_name.startswith("confluent-context-engine")
    assert server_config["url"].endswith("/kafka-clusters/lkc-xyz")


async def test_get_tools_raises_when_server_returns_nothing(component):
    with (
        patch(UPDATE_TOOLS_TARGET, new=AsyncMock(return_value=("", [], {}))),
        pytest.raises(ValueError, match="No tools"),
    ):
        await component._get_tools()


async def test_run_tool_executes_selected_tool_with_json_arguments(component):
    tools = [_tool("query_data")]
    component.tool = "query_data"
    component.tool_arguments = json.dumps({"topic": "orders", "filter": "amount > 10"})
    with patch(UPDATE_TOOLS_TARGET, new=_engine(tools)):
        frame = await component.run_tool()
    assert frame.to_dict(orient="records") == [{"echo": {"topic": "orders", "filter": "amount > 10"}}]


async def test_run_tool_requires_a_selection(component):
    with pytest.raises(ValueError, match="Select a tool"):
        await component.run_tool()


async def test_run_tool_unknown_tool_lists_available(component):
    tools = [_tool("list_topics")]
    component.tool = "nope"
    with (
        patch(UPDATE_TOOLS_TARGET, new=_engine(tools)),
        pytest.raises(ValueError, match="Available tools: list_topics"),
    ):
        await component.run_tool()


def test_tool_arguments_must_be_json_object(component):
    component.tool_arguments = "[1, 2]"
    with pytest.raises(TypeError, match="JSON object"):
        component._parse_tool_arguments()
    component.tool_arguments = "{not json"
    with pytest.raises(ValueError, match="JSON object"):
        component._parse_tool_arguments()


async def test_update_build_config_refreshes_tool_options(component):
    tools = [_tool("list_topics"), _tool("get_metadata"), _tool("query_data"), _tool("new_tool")]
    build_config = {"tool": {"options": list(CONTEXT_ENGINE_TOOLS), "value": "query_data"}}
    with patch(UPDATE_TOOLS_TARGET, new=_engine(tools)):
        out = await component.update_build_config(build_config, "", field_name="tool")
    assert out["tool"]["options"] == ["list_topics", "get_metadata", "query_data", "new_tool"]
    assert out["tool"]["value"] == "query_data"


async def test_update_build_config_keeps_defaults_on_failure(component):
    build_config = {"tool": {"options": list(CONTEXT_ENGINE_TOOLS), "value": ""}}
    with patch(UPDATE_TOOLS_TARGET, new=AsyncMock(side_effect=ConnectionError("down"))):
        out = await component.update_build_config(build_config, "", field_name="tool")
    assert out["tool"]["options"] == CONTEXT_ENGINE_TOOLS


def test_result_rows_flattens_json_array_and_keeps_text():
    result = SimpleNamespace(
        content=[
            SimpleNamespace(type="text", text=json.dumps([{"topic": "a"}, {"topic": "b"}])),
            SimpleNamespace(type="text", text="plain text"),
            SimpleNamespace(type="text", text=json.dumps(42)),
        ]
    )
    rows = ConfluentContextEngineComponent._result_rows(result)
    assert rows[0] == {"topic": "a"}
    assert rows[1] == {"topic": "b"}
    assert rows[2]["text"] == "plain text"
    assert rows[3] == {"type": "text", "text": "42", "parsed_value": 42}

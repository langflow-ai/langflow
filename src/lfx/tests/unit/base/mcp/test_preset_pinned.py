"""Pinned-mode behavior of ``MCPPresetComponent``.

``update_tools`` is patched so no MCP server is contacted; the doubles carry the
raw JSON Schemas on ``metadata`` exactly as the engine now does.  One test
(``test_the_guard_rides_on_the_real_tool_the_engine_builds``) deliberately runs
``update_tools`` for real against a fake transport, so the pinned-argument guard
is exercised on the actual pydantic ``MCPStructuredTool`` rather than on a
double.  The last two tests are the regression guard for the two shipped,
*unpinned* consumers (``lfx-confluent`` and ``lfx-ibm``): a component that does
not override ``_pinned_spec`` must behave exactly as it did before pinned mode
existed.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.tools import StructuredTool
from lfx.base.mcp.pinned import PinnedServerSpec, PinnedToolSpec, tools_list_digest
from lfx.base.mcp.preset import MCPPresetComponent, preset_control_inputs
from lfx.base.mcp.util import MCPServerInfo
from lfx.integrations.errors import IncompatibleToolError
from lfx.io import StrInput

UPDATE_TOOLS_TARGET = "lfx.base.mcp.preset.update_tools"
PINNED_URL = "https://mcp.example.com/mcp"

SEARCH_INPUT = {
    "type": "object",
    "properties": {"query": {"type": "string"}, "limit": {"type": "integer"}},
    "required": ["query"],
    "additionalProperties": False,
}
SEARCH_OUTPUT = {"type": "object", "properties": {"messages": {"type": "array"}}}


def _tool(name: str, input_schema: dict | None = None, output_schema: dict | None = None):
    calls: list[dict] = []

    async def coroutine(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=json.dumps({"tool": name, "args": kwargs}))])

    return SimpleNamespace(
        name=name,
        description=name,
        coroutine=coroutine,
        metadata={
            "server_name": "pinned-server",
            "input_schema": SEARCH_INPUT if input_schema is None else input_schema,
            "output_schema": SEARCH_OUTPUT if output_schema is None else output_schema,
        },
        calls=calls,
    )


def _engine(tools):
    return AsyncMock(return_value=("Streamable_HTTP", tools, {t.name: t for t in tools}))


def _spec(**overrides) -> PinnedServerSpec:
    base = {
        "server_url": PINNED_URL,
        "tools": (PinnedToolSpec(name="search_messages", input_schema=SEARCH_INPUT, output_schema=SEARCH_OUTPUT),),
    }
    return PinnedServerSpec(**{**base, **overrides})


class _PinnedPreset(MCPPresetComponent):
    display_name = "Pinned Preset"
    description = "test"
    icon = "Mcp"
    name = "PinnedPreset"
    integration_provider_id = "example"
    inputs = [
        StrInput(name="endpoint", display_name="Endpoint"),
        *preset_control_inputs(["search_messages"], tool_info="t"),
    ]
    pin: PinnedServerSpec | None = None

    def _mcp_server_config(self):
        return "pinned-server", {"url": self.endpoint, "headers": {"Authorization": "Bearer t"}}

    def _pinned_spec(self):
        return self.pin


class _UnpinnedPreset(_PinnedPreset):
    name = "UnpinnedPreset"

    def _pinned_spec(self):
        return None


@pytest.fixture
def pinned() -> _PinnedPreset:
    component = _PinnedPreset()
    component.endpoint = ""
    component.pin = _spec()
    component.tool = "search_messages"
    component.tool_arguments = "{}"
    component.tool_execution_timeout = 0.0
    component.verify_ssl = True
    return component


# ------------------------------------------------------------------ discovery
async def test_pinned_load_accepts_an_exactly_matching_server(pinned):
    with patch(UPDATE_TOOLS_TARGET, new=_engine([_tool("search_messages")])) as engine:
        tools = await pinned._get_tools()
    assert [t.name for t in tools] == ["search_messages"]
    _, config = engine.await_args.args[:2]
    assert config["url"] == PINNED_URL
    assert config["mode"] == "Streamable_HTTP"
    # The transport is part of the pin: no silent SSE fallback behind it.
    assert config["allow_sse_fallback"] is False
    assert config["headers"] == {"Authorization": "Bearer t"}


async def test_pinned_load_rejects_an_added_tool(pinned):
    tools = [_tool("search_messages"), _tool("delete_message")]
    with patch(UPDATE_TOOLS_TARGET, new=_engine(tools)), pytest.raises(IncompatibleToolError) as excinfo:
        await pinned._get_tools()
    assert excinfo.value.details["added"] == ["delete_message"]
    assert excinfo.value.provider == "example"


async def test_pinned_load_rejects_a_removed_tool(pinned):
    with (
        patch(UPDATE_TOOLS_TARGET, new=AsyncMock(return_value=("", [], {}))),
        pytest.raises(IncompatibleToolError) as excinfo,
    ):
        await pinned._get_tools()
    assert excinfo.value.details["removed"] == ["search_messages"]


async def test_pinned_load_rejects_argument_schema_drift(pinned):
    widened = {**SEARCH_INPUT, "properties": {**SEARCH_INPUT["properties"], "cursor": {"type": "string"}}}
    with (
        patch(UPDATE_TOOLS_TARGET, new=_engine([_tool("search_messages", widened)])),
        pytest.raises(IncompatibleToolError) as excinfo,
    ):
        await pinned._get_tools()
    assert excinfo.value.details["changed"] == ["search_messages: argument schema"]


async def test_pinned_load_rejects_a_server_version_mismatch(pinned):
    pinned.pin = _spec(server_version="2.1.0")
    pinned._streamable_http_client = SimpleNamespace(server_info=MCPServerInfo(name="example", version="2.2.0"))
    with (
        patch(UPDATE_TOOLS_TARGET, new=_engine([_tool("search_messages")])),
        pytest.raises(IncompatibleToolError) as excinfo,
    ):
        await pinned._get_tools()
    assert excinfo.value.details["server"] == ["server version 2.2.0 does not match the pinned 2.1.0"]


async def test_pinned_load_accepts_a_matching_digest_and_version(pinned):
    tools = [_tool("search_messages")]
    pinned.pin = _spec(server_version="2.1.0", tools_list_hash=tools_list_digest(tools))
    pinned._streamable_http_client = SimpleNamespace(server_info=MCPServerInfo(name="example", version="2.1.0"))
    with patch(UPDATE_TOOLS_TARGET, new=_engine(tools)):
        assert [t.name for t in await pinned._get_tools()] == ["search_messages"]


async def test_pinned_component_refuses_an_endpoint_the_pin_does_not_name(pinned):
    pinned.endpoint = "https://evil.example.net/mcp"
    with (
        patch(UPDATE_TOOLS_TARGET, new=_engine([_tool("search_messages")])) as engine,
        pytest.raises(IncompatibleToolError) as excinfo,
    ):
        await pinned._get_tools()
    assert engine.await_count == 0
    assert excinfo.value.details["pinned_url"] == PINNED_URL


# ------------------------------------------------------------------ call time
async def test_pinned_run_tool_executes_and_flattens_the_result(pinned):
    pinned.tool_arguments = '{"query": "orders"}'
    with patch(UPDATE_TOOLS_TARGET, new=_engine([_tool("search_messages")])):
        frame = await pinned.run_tool()
    assert frame.to_dict(orient="records") == [{"tool": "search_messages", "args": {"query": "orders"}}]


async def test_pinned_run_tool_rejects_arguments_outside_the_pinned_schema(pinned):
    """Discovery-time checks are not enough: the engine forwards unknown keys."""
    pinned.tool_arguments = '{"query": "orders", "cursor": "abc"}'
    tool = _tool("search_messages")
    with patch(UPDATE_TOOLS_TARGET, new=_engine([tool])), pytest.raises(IncompatibleToolError) as excinfo:
        await pinned.run_tool()
    assert excinfo.value.details["unexpected"] == ["cursor"]
    assert tool.calls == []


async def test_pinned_tool_mode_guard_survives_the_toolset_handoff(pinned):
    """The Agent calls the Toolset coroutine directly, so the guard must ride on it."""
    with patch(UPDATE_TOOLS_TARGET, new=_engine([_tool("search_messages")])):
        tools = await pinned._get_tools()
    with pytest.raises(IncompatibleToolError):
        await tools[0].coroutine(query="orders", cursor="abc")
    result = await tools[0].coroutine(query="orders")
    assert json.loads(result.content[0].text)["args"] == {"query": "orders"}


class _EngineClient:
    """Enough of ``MCPStreamableHttpClient`` for ``update_tools`` to run for real."""

    def __init__(self, tools):
        self._tools = tools
        self._connected = True
        self.server_info = None
        self.calls: list[tuple[str, dict]] = []
        self.connected_with: dict = {}

    async def connect_to_server(self, url, headers=None, verify_ssl=True, allow_sse_fallback=True):  # noqa: ARG002, FBT002
        self.connected_with = {"url": url, "headers": headers, "allow_sse_fallback": allow_sse_fallback}
        return self._tools

    async def run_tool(self, tool_name, arguments=None):
        self.calls.append((tool_name, dict(arguments or {})))
        text = json.dumps({"tool": tool_name, "args": arguments})
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)])


def _server_tool(name: str):
    """A discovered tool in the shape ``update_tools`` receives from the SDK."""
    return SimpleNamespace(name=name, description=name, inputSchema=SEARCH_INPUT, outputSchema=SEARCH_OUTPUT)


async def test_the_guard_rides_on_the_real_tool_the_engine_builds(pinned):
    """Every other test here uses doubles; this one runs ``update_tools`` for real.

    ``_guarded_tool`` assigns onto a live pydantic ``MCPStructuredTool``, and both
    of that tool's call paths -- the async ``coroutine`` the Agent and ``run_tool``
    use, and the synchronous ``func`` -- must carry the pinned-argument check.
    """
    client = _EngineClient([_server_tool("search_messages")])
    pinned._streamable_http_client = client
    with patch("lfx.base.mcp.util.validate_connector_url_for_ssrf", new=lambda _url: None):
        tools, _ = await pinned._load_tools()

    tool = tools[0]
    assert isinstance(tool, StructuredTool)
    assert client.connected_with["url"] == PINNED_URL
    assert client.connected_with["allow_sse_fallback"] is False

    with pytest.raises(IncompatibleToolError):
        await tool.coroutine(query="orders", cursor="abc")
    with pytest.raises(IncompatibleToolError):
        tool.func(query="orders", cursor="abc")
    assert client.calls == []

    await tool.coroutine(query="orders")
    assert client.calls == [("search_messages", {"query": "orders"})]


async def test_a_missing_required_argument_is_not_reported_as_provider_drift(pinned):
    """An omitted field reaches the tool, whose own args schema rejects it.

    The doubles here accept anything, so what this pins is that the guard does
    NOT convert a caller-side omission into a non-retryable ``incompatible-tool``
    telling the operator to upgrade a bundle.
    """
    tool = _tool("search_messages")
    with patch(UPDATE_TOOLS_TARGET, new=_engine([tool])):
        await pinned.run_tool()
    assert tool.calls == [{}]


# ---------------------------------------------------------------- build config
async def test_pinned_dropdown_never_takes_options_from_the_live_server(pinned):
    build_config = {"tool": {"options": ["search_messages"], "value": "search_messages"}}
    with patch(UPDATE_TOOLS_TARGET, new=_engine([_tool("renamed_search")])) as engine:
        out = await pinned.update_build_config(build_config, "", field_name="tool")
    assert engine.await_count == 0
    assert out["tool"]["options"] == ["search_messages"]
    assert out["tool"]["value"] == "search_messages"


async def test_pinned_dropdown_clears_a_saved_value_outside_the_pin(pinned):
    build_config = {"tool": {"options": ["stale"], "value": "stale"}}
    with patch(UPDATE_TOOLS_TARGET, new=_engine([_tool("search_messages")])):
        out = await pinned.update_build_config(build_config, "", field_name="tool")
    assert out["tool"]["options"] == ["search_messages"]
    assert out["tool"]["value"] == ""


# ------------------------------------------------------------------ regression
def test_the_base_class_is_unpinned_by_default():
    assert MCPPresetComponent._pinned_spec(MCPPresetComponent.__new__(MCPPresetComponent)) is None


async def test_unpinned_presets_keep_discovery_behavior_untouched():
    component = _UnpinnedPreset()
    component.endpoint = "https://vendor.example.com/mcp"
    component.tool = ""
    component.tool_arguments = "{}"
    component.tool_execution_timeout = 0.0
    component.verify_ssl = True

    tools = [_tool("a"), _tool("c")]
    with patch(UPDATE_TOOLS_TARGET, new=_engine(tools)) as engine:
        got = await component._get_tools()
        out = await component.update_build_config(
            {"tool": {"options": ["a", "b"], "value": "b"}}, "", field_name="tool"
        )
    assert [t.name for t in got] == ["a", "c"]
    _, config = engine.await_args.args[:2]
    assert config["url"] == "https://vendor.example.com/mcp"
    assert "allow_sse_fallback" not in config
    # The live refresh still rewrites the dropdown for unpinned consumers.
    assert out["tool"]["options"] == ["a", "c"]
    assert out["tool"]["value"] == ""

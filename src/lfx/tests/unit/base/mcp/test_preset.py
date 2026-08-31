"""Unit tests for ``lfx.base.mcp.preset.MCPPresetComponent``.

The base is exercised through a minimal subclass; ``update_tools`` is patched
so no MCP server is contacted.  Covers the sync/async ``_mcp_server_config``
contract, the Tool-Mode entrypoint, the direct-run output, argument parsing,
result flattening, and the dropdown refresh.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from lfx.base.mcp.preset import TOOL_MODE_TRIGGER, MCPPresetComponent, preset_control_inputs
from lfx.io import StrInput

UPDATE_TOOLS_TARGET = "lfx.base.mcp.preset.update_tools"


def _tool(name: str, payload=None):
    async def coroutine(**kwargs):
        text = json.dumps(payload if payload is not None else {"tool": name, "args": kwargs})
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)])

    return SimpleNamespace(name=name, description=name, coroutine=coroutine)


def _engine(tools):
    return AsyncMock(return_value=("Streamable_HTTP", tools, {t.name: t for t in tools}))


class _SyncPreset(MCPPresetComponent):
    display_name = "Sync Preset"
    description = "test"
    icon = "Mcp"
    name = "SyncPreset"
    inputs = [StrInput(name="endpoint", display_name="Endpoint"), *preset_control_inputs(["a", "b"], tool_info="t")]

    def _mcp_server_config(self):
        return "sync-server", {"url": self.endpoint, "headers": {"X-Test": "1"}, "mode": "Streamable_HTTP"}


class _AsyncPreset(_SyncPreset):
    name = "AsyncPreset"

    async def _mcp_server_config(self):
        return "async-server", {"url": self.endpoint, "mode": "Streamable_HTTP"}


@pytest.fixture
def sync_component() -> _SyncPreset:
    c = _SyncPreset()
    c.endpoint = "https://mcp.example.com/mcp"
    c.tool = ""
    c.tool_arguments = "{}"
    c.tool_execution_timeout = 0.0
    c.verify_ssl = True
    return c


def test_preset_control_inputs_shape():
    inputs = preset_control_inputs(["x", "y"], tool_info="info")
    names = [i.name for i in inputs]
    assert names == ["tool", "tool_arguments", "tool_execution_timeout", "verify_ssl", TOOL_MODE_TRIGGER]
    tool = inputs[0]
    assert tool.options == ["x", "y"]
    assert tool.refresh_button is True
    trigger = inputs[-1]
    assert trigger.tool_mode is True
    assert trigger.show is False


def test_base_declares_tool_output_and_response_output():
    assert MCPPresetComponent.add_tool_output is True
    assert [o.name for o in MCPPresetComponent.outputs] == ["response"]


async def test_get_tools_with_sync_config(sync_component):
    tools = [_tool("a"), _tool("b")]
    with patch(UPDATE_TOOLS_TARGET, new=_engine(tools)) as upd:
        got = await sync_component._get_tools()
    assert [t.name for t in got] == ["a", "b"]
    name, config = upd.await_args.args[:2]
    assert name == "sync-server"
    assert config["headers"] == {"X-Test": "1"}
    assert upd.await_args.kwargs["tool_execution_timeout"] is None


async def test_get_tools_with_async_config():
    c = _AsyncPreset()
    c.endpoint = "https://mcp.example.com/mcp"
    c.tool_execution_timeout = 12.5
    tools = [_tool("a")]
    with patch(UPDATE_TOOLS_TARGET, new=_engine(tools)) as upd:
        got = await c._get_tools()
    assert [t.name for t in got] == ["a"]
    assert upd.await_args.args[0] == "async-server"
    assert upd.await_args.kwargs["tool_execution_timeout"] == 12.5


async def test_get_tools_raises_when_engine_returns_nothing(sync_component):
    with (
        patch(UPDATE_TOOLS_TARGET, new=AsyncMock(return_value=("", [], {}))),
        pytest.raises(ValueError, match="No tools"),
    ):
        await sync_component._get_tools()


async def test_run_tool_executes_selected_tool(sync_component):
    tools = [_tool("a")]
    sync_component.tool = "a"
    sync_component.tool_arguments = '{"q": 1}'
    with patch(UPDATE_TOOLS_TARGET, new=_engine(tools)):
        frame = await sync_component.run_tool()
    assert frame.to_dict(orient="records") == [{"tool": "a", "args": {"q": 1}}]


async def test_run_tool_requires_selection_and_known_tool(sync_component):
    with pytest.raises(ValueError, match="Select a tool"):
        await sync_component.run_tool()
    sync_component.tool = "zzz"
    with patch(UPDATE_TOOLS_TARGET, new=_engine([_tool("a")])), pytest.raises(ValueError, match="Available tools: a"):
        await sync_component.run_tool()


def test_parse_tool_arguments_accepts_dict_json_and_empty(sync_component):
    sync_component.tool_arguments = {"k": "v"}
    assert sync_component._parse_tool_arguments() == {"k": "v"}
    sync_component.tool_arguments = ""
    assert sync_component._parse_tool_arguments() == {}
    sync_component.tool_arguments = '{"k": 2}'
    assert sync_component._parse_tool_arguments() == {"k": 2}
    sync_component.tool_arguments = "[]"
    with pytest.raises(TypeError, match="JSON object"):
        sync_component._parse_tool_arguments()
    sync_component.tool_arguments = "{oops"
    with pytest.raises(ValueError, match="JSON object"):
        sync_component._parse_tool_arguments()


def test_result_rows_handles_models_dicts_arrays_and_plain_text():
    class _Block:
        def __init__(self, type_, text):
            self._d = {"type": type_, "text": text}

        def model_dump(self):
            return dict(self._d)

    result = SimpleNamespace(
        content=[
            _Block("text", json.dumps({"a": 1})),
            _Block("text", json.dumps([{"b": 1}, {"b": 2}])),
            _Block("text", "hello"),
            _Block("text", json.dumps([1, 2])),
            {"type": "image", "data": "..."},
            "raw",
        ]
    )
    rows = MCPPresetComponent._result_rows(result)
    assert rows[0] == {"a": 1}
    assert rows[1:3] == [{"b": 1}, {"b": 2}]
    assert rows[3] == {"type": "text", "text": "hello"}
    assert rows[4] == {"type": "text", "text": "[1, 2]", "parsed_value": [1, 2]}
    assert rows[5] == {"type": "image", "data": "..."}
    assert rows[6] == {"type": "text", "text": "raw"}
    assert MCPPresetComponent._result_rows(None) == []


async def test_update_build_config_refreshes_and_clears_stale_value(sync_component):
    build_config = {"tool": {"options": ["a", "b"], "value": "b"}}
    with patch(UPDATE_TOOLS_TARGET, new=_engine([_tool("a"), _tool("c")])):
        out = await sync_component.update_build_config(build_config, "", field_name="tool")
    assert out["tool"]["options"] == ["a", "c"]
    assert out["tool"]["value"] == ""


async def test_update_build_config_ignores_other_fields_and_failures(sync_component):
    build_config = {"tool": {"options": ["a", "b"], "value": "b"}}
    with patch(UPDATE_TOOLS_TARGET, new=AsyncMock(side_effect=OSError("down"))) as upd:
        out = await sync_component.update_build_config(dict(build_config), "x", field_name="endpoint")
        assert upd.await_count == 0
        out = await sync_component.update_build_config(dict(build_config), "", field_name="tool")
    assert out["tool"] == {"options": ["a", "b"], "value": "b"}


def test_resolved_timeout_handles_zero_negative_and_garbage(sync_component):
    sync_component.tool_execution_timeout = 0
    assert sync_component._resolved_timeout() is None
    sync_component.tool_execution_timeout = -3
    assert sync_component._resolved_timeout() is None
    sync_component.tool_execution_timeout = "abc"
    assert sync_component._resolved_timeout() is None
    sync_component.tool_execution_timeout = 4
    assert sync_component._resolved_timeout() == 4.0

from typing import Any

import pytest
from langchain_core.tools import StructuredTool
from langflow.base.mcp.base_client import BaseMCPClient
from langflow.base.mcp.util import (
    ToolCatalogue,
    _detect_mode,
    update_tools,
)

# ---------------------------------------------------------------------------
# Utility helpers under test
# ---------------------------------------------------------------------------


class DummyTool:  # Minimal stand-in for mcp.types.Tool
    def __init__(self, name: str = "dummy_tool") -> None:
        self.name = name
        self.description = "A dummy tool for tests"
        self.inputSchema = {
            "type": "object",
            "properties": {},
            "required": [],
        }


class _BaseClientStub(BaseMCPClient[dict[str, Any]]):
    """Common stub logic for STDIO and SSE fakes."""

    def __init__(self, tool_name: str = "dummy_tool") -> None:
        super().__init__()
        self._tool_obj = DummyTool(name=tool_name)

    async def _execute_tool(self, tool_name: str, arguments: dict[str, Any]):
        """Return echo payload so the call path is exercised."""
        return {"ran": tool_name, "args": arguments}


class DummyStdioClient(_BaseClientStub):
    async def connect_to_server(self, command_str: str, env: dict | None = None):  # noqa: ARG002
        self._connected = True
        # Simulate negotiated protocol metadata
        self.protocol_info = {"protocol_version": "dummy_stdio"}
        return [self._tool_obj]


class DummySseClient(_BaseClientStub):
    async def connect_to_server(self, url: str, headers: dict | None = None):  # noqa: ARG002
        self._connected = True
        self.protocol_info = {"protocol_version": "dummy_sse"}
        return [self._tool_obj]


# ---------------------------------------------------------------------------
# Tests for _detect_mode
# ---------------------------------------------------------------------------


def test_detect_mode_valid():
    assert _detect_mode({"command": "echo 1"}) == "Stdio"
    assert _detect_mode({"url": "https://example.com"}) == "SSE"


def test_detect_mode_errors():
    with pytest.raises(ValueError, match="empty"):
        _detect_mode({})  # empty config
    with pytest.raises(ValueError, match="Ambiguous"):
        _detect_mode({"command": "echo", "url": "https://example.com"})  # ambiguous


# ---------------------------------------------------------------------------
# Tests for update_tools (happy path)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_tools_stdio_happy():
    cfg = {"command": "echo ok"}
    cat: ToolCatalogue = await update_tools(
        "test_server",
        cfg,
        mcp_stdio_client=DummyStdioClient(tool_name="echo"),
    )

    assert cat.mode == "Stdio"
    assert isinstance(cat.tools, list)
    assert len(cat.tools) == 1
    assert isinstance(cat.tools[0], StructuredTool)
    # Named-tuple attribute / old tuple index both work
    assert cat.tools[0].name == "echo"
    assert cat.tool_cache["echo"] is cat.tools[0]
    assert cat.protocol_info.get("protocol_version") == "dummy_stdio"


@pytest.mark.asyncio
async def test_update_tools_sse_happy():
    cfg = {"url": "https://example.com"}
    cat: ToolCatalogue = await update_tools(
        "sse_server",
        cfg,
        mcp_sse_client=DummySseClient(tool_name="ping"),
    )

    assert cat.mode == "SSE"
    assert len(cat.tools) == 1
    assert cat.tools[0].name == "ping"
    assert cat.tool_cache["ping"].name == "ping"
    assert cat.protocol_info.get("protocol_version") == "dummy_sse"


# ---------------------------------------------------------------------------
# update_tools - error scenarios
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_tools_bad_config():
    # Missing both command and url
    with pytest.raises(ValueError, match="Server configuration is empty|Incomplete"):
        await update_tools("bad_server", {}, mcp_stdio_client=DummyStdioClient())


@pytest.mark.asyncio
async def test_update_tools_no_tools():
    class EmptyClient(DummyStdioClient):
        async def connect_to_server(self, command_str: str, env: dict | None = None):  # noqa: ARG002
            self._connected = True
            self.protocol_info = {}
            return []  # No tools

    with pytest.raises(ConnectionError, match="No tools reported"):
        await update_tools("empty", {"command": "echo"}, mcp_stdio_client=EmptyClient())

"""MCP dispatch and lifecycle must not start or call product analytics."""

from __future__ import annotations

from typing import Any

import pytest
from mcp.server.fastmcp.exceptions import ToolError


class _RecordingTelemetry:
    """Compatibility-shaped recorder that also records swallowed attempts."""

    instances: list[_RecordingTelemetry] = []

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        self.calls: list[str] = []
        type(self).instances.append(self)

    def start(self) -> None:
        self.calls.append("start")

    async def stop(self) -> None:
        self.calls.append("stop")

    async def log_mcp_tool(self, _payload: Any) -> None:
        self.calls.append("log_mcp_tool")

    async def send_telemetry_data(self, _payload: Any, _path: str | None = None) -> None:
        self.calls.append("send_telemetry_data")


class _MCPClient:
    server_url = "http://langflow.test"

    async def get(self, path: str, **_kwargs: Any) -> Any:
        if path == "/flows/":
            return [
                {
                    "id": "flow-1",
                    "name": "Recorded flow",
                    "description": "",
                    "data": {"nodes": [], "edges": []},
                }
            ]
        msg = "recorded failure"
        raise RuntimeError(msg)


@pytest.mark.parametrize("do_not_track", [None, "false", "true"], ids=["absent", "false", "true"])
async def test_fastmcp_dispatch_does_not_resolve_or_call_telemetry(
    monkeypatch: pytest.MonkeyPatch,
    do_not_track: str | None,
) -> None:
    """Real FastMCP dispatch returns normal results/errors without analytics hooks."""
    from lfx.mcp import server

    if do_not_track is None:
        monkeypatch.delenv("LANGFLOW_DO_NOT_TRACK", raising=False)
    else:
        monkeypatch.setenv("LANGFLOW_DO_NOT_TRACK", do_not_track)
    monkeypatch.delenv("LANGFLOW_TELEMETRY_BASE_URL", raising=False)
    _RecordingTelemetry.instances.clear()
    # The current server has no TelemetryService attribute. Installing this
    # recorder with ``raising=False`` also catches the historical server's
    # direct constructor, lifecycle, and decorated MCP calls.
    monkeypatch.setattr(server, "TelemetryService", _RecordingTelemetry, raising=False)

    with server.client_scope(_MCPClient()):
        async with server.mcp._mcp_server.lifespan(server.mcp._mcp_server):
            successful = await server.mcp.call_tool("list_flows", {})
            assert successful[1]["result"][0]["id"] == "flow-1"

            with pytest.raises(ToolError, match="recorded failure"):
                await server.mcp.call_tool("get_flow_info", {"flow_id": "missing"})

    assert _RecordingTelemetry.instances == []

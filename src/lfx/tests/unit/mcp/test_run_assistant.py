"""run_assistant on the lfx MCP server: the assistant consumed through the REST API.

The tool streams the HEADLESS route ``/agentic/assist/run`` with the caller's own
credentials (no ``user_id`` argument — identity comes from the API key), forwards
progress events to the MCP client, and returns the assistant's final payload.
``/assist/run`` (not ``/assist/stream``) is what applies the canvas changes: the
stream route leaves them as a UI proposal an MCP caller could never approve.
"""

from unittest.mock import AsyncMock

import pytest
from lfx.mcp import server as mcp_server


def _fake_client(events, seen=None):
    client = AsyncMock()

    async def stream(path, json_data=None, timeout=None):  # noqa: ARG001
        if seen is not None:
            seen["path"] = path
            seen["payload"] = json_data
        for event in events:
            yield event

    client.stream_post = stream
    client.post = AsyncMock()
    return client


@pytest.fixture(autouse=True)
def _reset_client():
    yield
    mcp_server._client_var.set(None)


async def test_run_assistant_hits_the_headless_route_and_returns_complete():
    events = [
        {"event": "progress", "step": "analyzing", "message": "Analyzing request"},
        {"event": "progress", "step": "building", "message": "Building flow"},
        {"event": "complete", "data": {"result": "done!", "flow_changed": True, "flow_id": "flow-1"}},
    ]
    seen: dict = {}
    client = _fake_client(events, seen)
    mcp_server._set_client(client)

    result = await mcp_server.run_assistant(instruction="build me a flow", flow_id="flow-1")

    # The headless route is what persists the canvas; /assist/stream would only propose.
    assert seen["path"] == "/agentic/assist/run"
    assert seen["payload"] == {"instruction": "build me a flow", "flow_id": "flow-1"}
    assert result["result"] == "done!"
    assert result["flow_changed"] is True
    assert result["flow_id"] == "flow-1"
    assert result["link"] == "/flow/flow-1"
    # The server creates the flow when needed; the tool must not pre-create one.
    client.post.assert_not_awaited()


async def test_run_assistant_omits_absent_optional_fields():
    seen: dict = {}
    client = _fake_client([{"event": "complete", "data": {"result": "ok", "flow_id": "made-by-server"}}], seen)
    mcp_server._set_client(client)

    result = await mcp_server.run_assistant(instruction="new flow please", provider="OpenAI")

    assert seen["payload"] == {"instruction": "new flow please", "provider": "OpenAI"}
    assert result["flow_id"] == "made-by-server"


async def test_run_assistant_raises_on_error_event():
    events = [{"event": "error", "message": "model exploded"}]
    client = _fake_client(events)
    mcp_server._set_client(client)

    with pytest.raises(RuntimeError, match="model exploded"):
        await mcp_server.run_assistant(instruction="boom", flow_id="flow-1")


async def test_client_scope_sets_and_resets_only_the_contextvar():
    outer = AsyncMock()
    inner = AsyncMock()
    mcp_server._set_client(outer)
    with mcp_server.client_scope(inner):
        assert mcp_server._get_client() is inner
    assert mcp_server._get_client() is outer

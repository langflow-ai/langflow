import pytest
from langflow.base.mcp.sse_client import MCPSseClient

pytestmark = pytest.mark.asyncio


@pytest.mark.usefixtures("http_sse_url")
async def test_http_sse_legacy_endpoint(http_sse_url):
    """Connecting directly to the legacy /sse discovery stream should succeed.

    MCPSseClient must skip the Streamable-HTTP probe when the server already
    advertises *text/event-stream* and fall back to the HTTP+SSE transport.
    The reference server exposes two tools: *echo* and *simulate_error*.
    """
    client = MCPSseClient()
    try:
        tools = await client.connect_to_server(http_sse_url)
        names = [t.name for t in tools]
        assert "echo" in names
        assert "simulate_error" in names
    finally:
        await client.disconnect()

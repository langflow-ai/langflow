import pytest

pytestmark = pytest.mark.asyncio


@pytest.mark.usefixtures("http_sse_url")
async def test_http_sse_legacy_endpoint():
    pytest.xfail("Client needs fallback bypass for /sse URL - to be implemented.")

    # client = MCPSseClient()
    # tools = await client.connect_to_server(http_sse_url)
    # names = [t.name for t in tools]
    # assert "echo" in names and "simulate_error" in names
    # await client.disconnect()

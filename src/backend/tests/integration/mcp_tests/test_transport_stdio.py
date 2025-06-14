import pytest
from langflow.base.mcp.stdio_client import MCPStdioClient

pytestmark = pytest.mark.asyncio


async def test_reconnect_after_disconnect(stdio_reference_command):
    # First connection
    client1 = MCPStdioClient()
    await client1.connect_to_server(stdio_reference_command)
    res1 = await client1.call_tool("echo", {"message": "first"})
    assert "first" in str(res1).lower()
    await client1.disconnect()

    # Second connection
    client2 = MCPStdioClient()
    await client2.connect_to_server(stdio_reference_command)
    res2 = await client2.call_tool("echo", {"message": "second"})
    assert "second" in str(res2).lower()
    await client2.disconnect()

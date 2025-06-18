import pytest
from langflow.base.mcp.util import MCPStdioClient

pytestmark = pytest.mark.asyncio


async def test_reconnect_after_disconnect(stdio_reference_command):
    """Test that stdio clients can reconnect after disconnection."""
    # First connection
    client1 = MCPStdioClient()
    await client1.connect_to_server(stdio_reference_command)
    res1 = await client1.run_tool("echo", {"message": "first"})
    assert "first" in str(res1).lower()
    await client1.disconnect()

    # Second connection
    client2 = MCPStdioClient()
    await client2.connect_to_server(stdio_reference_command)
    res2 = await client2.run_tool("echo", {"message": "second"})
    assert "second" in str(res2).lower()
    await client2.disconnect()


async def test_stdio_client_context_manager(stdio_reference_command):
    """Test that stdio clients work as context managers."""
    async with MCPStdioClient() as client:
        await client.connect_to_server(stdio_reference_command)
        result = await client.run_tool("echo", {"message": "context_manager"})
        assert "context_manager" in str(result).lower() 
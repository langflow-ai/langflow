import pytest
from langflow.base.mcp.util import MCPStdioClient

pytestmark = pytest.mark.asyncio


async def test_reconnect_after_disconnect(stdio_reference_command):
    """Test that stdio clients can reconnect after disconnection."""
    # First connection
    client1 = MCPStdioClient()
    await client1.connect_to_server(stdio_reference_command)
    res1 = await client1.run_tool("echo", {"message": "first"})

    # Check canonical data field instead of string representation
    if isinstance(res1, dict) and "content" in res1:
        assert len(res1["content"]) > 0, f"Expected content array, got: {res1}"
        first_content = res1["content"][0]
        if isinstance(first_content, dict) and "text" in first_content:
            text = first_content["text"]
            assert "Echo: first" in text, f"Expected 'Echo: first' in text, got: {text}"
        else:
            # Handle dataclass/namespace style
            text_attr = getattr(first_content, "text", None)
            assert text_attr is not None, f"Expected text attribute, got: {text_attr}"
            assert "Echo: first" in text_attr, f"Expected 'Echo: first' in text attribute, got: {text_attr}"
    else:
        # Fallback to string representation if structure is unexpected
        assert "first" in str(res1).lower(), f"Unexpected result structure: {res1}"

    await client1.disconnect()

    # Second connection
    client2 = MCPStdioClient()
    await client2.connect_to_server(stdio_reference_command)
    res2 = await client2.run_tool("echo", {"message": "second"})

    # Check canonical data field instead of string representation
    if isinstance(res2, dict) and "content" in res2:
        assert len(res2["content"]) > 0, f"Expected content array, got: {res2}"
        second_content = res2["content"][0]
        if isinstance(second_content, dict) and "text" in second_content:
            text = second_content["text"]
            assert "Echo: second" in text, f"Expected 'Echo: second' in text, got: {text}"
        else:
            # Handle dataclass/namespace style
            text_attr = getattr(second_content, "text", None)
            assert text_attr is not None, f"Expected text attribute, got: {text_attr}"
            assert "Echo: second" in text_attr, f"Expected 'Echo: second' in text attribute, got: {text_attr}"
    else:
        # Fallback to string representation if structure is unexpected
        assert "second" in str(res2).lower(), f"Unexpected result structure: {res2}"

    await client2.disconnect()


async def test_stdio_client_context_manager(stdio_reference_command):
    """Test that stdio clients work as context managers."""
    async with MCPStdioClient() as client:
        await client.connect_to_server(stdio_reference_command)
        result = await client.run_tool("echo", {"message": "context_manager"})

        # Check canonical data field instead of string representation
        if isinstance(result, dict) and "content" in result:
            assert len(result["content"]) > 0, f"Expected content array, got: {result}"
            content_item = result["content"][0]
            if isinstance(content_item, dict) and "text" in content_item:
                text = content_item["text"]
                assert "Echo: context_manager" in text, f"Expected 'Echo: context_manager' in text, got: {text}"
            else:
                # Handle dataclass/namespace style
                text_attr = getattr(content_item, "text", None)
                assert text_attr is not None, f"Expected text attribute, got: {text_attr}"
                assert "Echo: context_manager" in text_attr, (
                    f"Expected 'Echo: context_manager' in text attribute, got: {text_attr}"
                )
        else:
            # Fallback to string representation if structure is unexpected
            assert "context_manager" in str(result).lower(), f"Unexpected result structure: {result}"

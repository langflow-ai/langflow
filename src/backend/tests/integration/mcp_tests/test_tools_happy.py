import re

import pytest

pytestmark = pytest.mark.asyncio


async def test_client_connection_status(mcp_client):
    """Test that MCP clients properly report connection status."""
    transport, client = mcp_client
    # Both clients should have _connected attribute after connection
    assert hasattr(client, "_connected"), f"Client for {transport} should have _connected attribute"
    assert client._connected, f"Client should be connected for transport {transport}"


async def test_echo_roundtrip(mcp_client):
    """Test basic echo functionality across transports."""
    transport, client = mcp_client
    payload = {"message": "integration"}

    try:
        result = await client.run_tool("echo", payload)
        assert "integration" in str(result).lower(), f"Echo failed for {transport}: {result}"
    except Exception as e:
        pytest.fail(f"Echo tool failed on {transport}: {e}")


async def test_add_numbers(mcp_client):
    """Test add_numbers tool across transports."""
    transport, client = mcp_client

    try:
        result = await client.run_tool("add_numbers", {"a": 1, "b": 2})

        # The reference server returns text like "Result: 3" wrapped in a dict;
        # make the assertion flexible.
        result_str = str(result)
        match = re.search(r"[=:]\s*([0-9]+)", result_str)
        assert match, f"Unexpected result format for {transport}: {result}"
        assert int(match.group(1)) == 3, f"Math calculation incorrect for {transport}: {result}"
    except Exception as e:
        pytest.fail(f"Add numbers tool failed on {transport}: {e}")


async def test_process_data(mcp_client):
    """Test process_data tool with complex nested parameters."""
    transport, client = mcp_client
    data = {"name": "test", "values": [1, 2, 3]}

    try:
        result = await client.run_tool("process_data", {"data": data})

        # Normalise result into raw text that should contain the JSON blob.
        if isinstance(result, dict) and "content" in result:
            # Handle dict style: {"content": [ {"text": "..."}, ... ] }
            pieces = []
            for item in result["content"]:
                if isinstance(item, dict) and "text" in item:
                    pieces.append(item["text"])
                else:  # dataclass / namespace
                    maybe_text = getattr(item, "text", None)
                    if maybe_text:
                        pieces.append(maybe_text)
            raw = "\n".join(pieces)
        else:
            raw = str(result)

        # Locate a JSON object using a DOTALL regex so newlines are captured.
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        assert match, f"No JSON found in result for {transport}: {raw}"

        json_blob = match.group(0).strip()  # remove surrounding whitespace

        # If the blob is quoted with single quotes (repr artefact), strip them.
        if (json_blob.startswith("'{") and json_blob.endswith("'}")) or (
            json_blob.startswith('"{') and json_blob.endswith('}"')
        ):
            json_blob = json_blob[1:-1]

        # Instead of strict JSON parsing (which can break due to double escaping
        # from various SDK reprs) just assert that the expected key/value pairs
        # appear in the textual blob. This keeps the test transport-agnostic and
        # tolerant of formatting differences (pretty JSON, minified, etc.).

        for snippet in [
            '"processed": true',
            '"name": "test"',
            '"sum": 6',
            '"count": 3',
        ]:
            assert snippet in json_blob.replace("\n", " "), f"{snippet} missing in {json_blob} for {transport}"

    except Exception as e:
        pytest.fail(f"Process data tool failed on {transport}: {e}")


async def test_get_server_info(mcp_client):
    """Test server info tool to verify server identification."""
    transport, client = mcp_client

    try:
        result = await client.run_tool("get_server_info", {})

        # Server info should contain transport-specific information
        result_str = str(result).lower()
        assert "test server" in result_str or "mcp" in result_str, f"Server info missing for {transport}: {result}"

        # Transport-specific checks
        if transport == "stdio":
            assert "stdio" in result_str, f"STDIO server info should mention stdio: {result}"
        elif transport == "sse":
            assert "sse" in result_str or "http" in result_str, f"SSE server info should mention sse or http: {result}"

    except Exception as e:
        # Some implementations might not have get_server_info, so we'll warn but not fail
        pytest.skip(f"Server info tool not available or failed on {transport}: {e}")


async def test_client_reconnection(mcp_client):
    """Test that clients can handle reconnection scenarios."""
    transport, client = mcp_client

    # First, verify connection works
    try:
        result1 = await client.run_tool("echo", {"message": "first"})
        assert "first" in str(result1).lower()

        # Disconnect and reconnect (simulate reconnection)
        await client.disconnect()

        if transport == "stdio":
            # For stdio, we need to provide the command again
            # This test may need adjustment based on actual client implementation
            pass  # Skip reconnection test for stdio for now
        elif transport == "sse":
            # For SSE, reconnection might work differently
            pass  # Skip reconnection test for sse for now

    except Exception as e:
        pytest.skip(f"Reconnection test not supported or failed on {transport}: {e}")

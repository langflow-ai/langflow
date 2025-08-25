"""Test script to verify header extraction functionality in MCP Tools component."""

import asyncio

from src.backend.base.langflow.base.mcp.util import _extract_headers_from_args


async def test_header_extraction():
    """Test that headers are correctly extracted from command line arguments."""
    # Test 1: Basic header extraction
    args = ["--headers", "x-api-key", "test-key", "--headers", "Authorization", "Bearer token123", "other-arg"]
    headers = _extract_headers_from_args(args)

    expected = {"x-api-key": "test-key", "authorization": "Bearer token123"}
    if headers != expected:
        msg = f"Test 1 failed: Expected {expected}, got {headers}"
        raise ValueError(msg)

    # Test 2: No headers
    args = ["some", "other", "args"]
    headers = _extract_headers_from_args(args)
    expected = {}
    if headers != expected:
        msg = f"Test 2 failed: Expected {expected}, got {headers}"
        raise ValueError(msg)

    # Test 3: Multiple headers with different cases
    args = ["--headers", "X-Custom-Header", "custom-value", "--headers", "Content-Type", "application/json"]
    headers = _extract_headers_from_args(args)
    expected = {"x-custom-header": "custom-value", "content-type": "application/json"}
    if headers != expected:
        msg = f"Test 3 failed: Expected {expected}, got {headers}"
        raise ValueError(msg)

    # Test 4: Malformed header args (should be ignored)
    args = ["--headers", "x-test", "value", "--headers", "malformed"]  # Missing value for malformed
    headers = _extract_headers_from_args(args)
    expected = {"x-test": "value"}
    if headers != expected:
        msg = f"Test 4 failed: Expected {expected}, got {headers}"
        raise ValueError(msg)


def test_stdio_server_config():
    """Test that STDIO server config correctly handles headers in args."""
    # Simulate server config with headers in args (like from the frontend)
    server_config = {
        "command": "npx -y @modelcontextprotocol/server-everything",
        "args": [
            "server",
            "--headers",
            "x-api-key",
            "test-key-123",
            "--headers",
            "Authorization",
            "Bearer token456",
            "--other-param",
            "value",
        ],
    }

    # Extract headers using our function
    headers = _extract_headers_from_args(server_config["args"])

    expected = {"x-api-key": "test-key-123", "authorization": "Bearer token456"}

    if headers != expected:
        msg = f"STDIO server config test failed: Expected {expected}, got {headers}"
        raise ValueError(msg)


if __name__ == "__main__":
    asyncio.run(test_header_extraction())
    test_stdio_server_config()

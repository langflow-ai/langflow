import contextlib

import pytest

pytestmark = pytest.mark.asyncio

# ExceptionGroup compatibility for Python <3.11
try:
    ExceptionGroupType = ExceptionGroup  # type: ignore[name-defined]
except NameError:
    ExceptionGroupType = ()

# Define exception types for MCP operations
MCP_EXC = (ValueError, RuntimeError, ExceptionGroupType)


async def _invoke_simulate_error(client, kind):
    """Helper that calls simulate_error and returns the error message if one occurred."""
    try:
        result = await client.run_tool("simulate_error", {"kind": kind})
    except MCP_EXC as exc:
        return str(exc)

    if isinstance(result, dict) and result.get("error"):
        return str(result["error"])
    return str(result)


@pytest.mark.parametrize("kind", ["validation", "runtime", "timeout"])
async def test_simulate_error_propagation(mcp_client, kind):
    """Test that different error types are properly propagated across transports."""
    transport, client = mcp_client
    result = await client.run_tool("simulate_error", {"kind": kind})
    assert hasattr(result, "isError"), f"Expected isError attribute for {transport}, got: {result}"
    assert result.isError, f"Expected error result for {transport}, got: {result}"
    assert hasattr(result, "content"), f"Expected content attribute in error result for {transport}"
    assert result.content, f"Expected non-empty content in error result for {transport}"
    error_texts = [item.text.lower() for item in result.content if hasattr(item, "text")]
    error_message = " ".join(error_texts)
    assert kind in error_message, f"Error type '{kind}' not found in error message for {transport}: {error_message}"


async def test_session_survives_error(mcp_client):
    """Test that MCP sessions remain functional after encountering errors."""
    transport, client = mcp_client
    try:
        _ = await _invoke_simulate_error(client, "runtime")
    except (ValueError, RuntimeError):
        pass
    except MCP_EXC as e:
        if "not found" in str(e).lower() or "unknown" in str(e).lower():
            pytest.skip(f"simulate_error tool not available on {transport}: {e}")
        else:
            raise
    echo_res = await client.run_tool("echo", {"message": "after-error"})
    assert "after-error" in str(echo_res).lower(), f"Session did not survive error on {transport}"


async def test_invalid_tool_name(mcp_client):
    """Test handling of invalid tool names."""
    transport, client = mcp_client
    # Unpack the tuple for pytest.raises
    if isinstance(MCP_EXC, tuple):
        with pytest.raises(MCP_EXC, match=r"not found|unknown|invalid|tool|error"):
            await client.run_tool("nonexistent_tool_12345", {})
    else:
        with pytest.raises(MCP_EXC, match=r"not found|unknown|invalid|tool|error"):
            await client.run_tool("nonexistent_tool_12345", {})


@pytest.mark.xfail(reason="ExceptionGroup wrapping in Python 3.11+ hides actual MCP error message")
async def test_invalid_parameters(mcp_client):
    """Test handling of invalid parameters for valid tools."""
    transport, client = mcp_client
    with pytest.raises(MCP_EXC, match=r"parameter|validation|schema|argument|invalid|required"):
        await client.run_tool("add_numbers", {"x": 1, "y": 2})


@pytest.mark.xfail(reason="ExceptionGroup wrapping in Python 3.11+ hides actual MCP error message")
async def test_missing_required_parameters(mcp_client):
    """Test handling of missing required parameters."""
    transport, client = mcp_client
    with pytest.raises(MCP_EXC, match=r"required|missing|parameter|validation|argument"):
        await client.run_tool("add_numbers", {})


@pytest.mark.xfail(reason="ExceptionGroup wrapping in Python 3.11+ hides actual MCP error message")
async def test_malformed_arguments(mcp_client):
    """Test handling of malformed argument types."""
    transport, client = mcp_client
    with pytest.raises(MCP_EXC, match=r"type|validation|invalid|number|parameter|schema"):
        await client.run_tool("add_numbers", {"a": "not_a_number", "b": "also_not_a_number"})


async def test_client_state_after_error(mcp_client):
    """Test that client remains in a good state after various errors."""
    transport, client = mcp_client
    assert client._connected, f"Client should be connected initially on {transport}"
    error_scenarios = [
        ("nonexistent_tool", {}),
        ("add_numbers", {}),
        ("echo", {"wrong_param": "value"}),
    ]
    for tool_name, params in error_scenarios:
        with contextlib.suppress(MCP_EXC):
            await client.run_tool(tool_name, params)
        assert client._connected, f"Client should remain connected after error with {tool_name} on {transport}"
    try:
        result = await client.run_tool("echo", {"message": "still_working"})
        assert "still_working" in str(result).lower(), f"Client not functional after errors on {transport}"
    except MCP_EXC as e:
        pytest.fail(f"Client not functional after error scenarios on {transport}: {e}")

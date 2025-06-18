import pytest

pytestmark = pytest.mark.asyncio


async def _invoke_simulate_error(client, kind):
    """Helper that calls simulate_error and returns the error message if one occurred."""
    try:
        result = await client.run_tool("simulate_error", {"error_type": kind})
    except Exception as exc:  # noqa: BLE001
        # Exception propagated - that counts as error handling
        return str(exc)

    # Some transports might embed error in JSON-RPC envelope instead of raising
    if isinstance(result, dict) and result.get("error"):
        return str(result["error"])
    return str(result)


@pytest.mark.parametrize("kind", ["validation", "runtime", "timeout"])
async def test_simulate_error_propagation(mcp_client, kind):
    """Test that different error types are properly propagated across transports."""
    transport, client = mcp_client

    try:
        msg = await _invoke_simulate_error(client, kind)
        # Should contain the error type somewhere in the message
        assert kind in msg.lower(), f"Error type '{kind}' not found in error message for {transport}: {msg}"
    except Exception as e:
        # If the tool doesn't exist, skip this test
        if "not found" in str(e).lower() or "unknown" in str(e).lower():
            pytest.skip(f"simulate_error tool not available on {transport}: {e}")
        else:
            raise


async def test_session_survives_error(mcp_client):
    """Test that MCP sessions remain functional after encountering errors."""
    transport, client = mcp_client

    # First, trigger a runtime error (if the tool exists)
    try:
        _ = await _invoke_simulate_error(client, "runtime")
    except Exception as e:
        if "not found" in str(e).lower() or "unknown" in str(e).lower():
            pytest.skip(f"simulate_error tool not available on {transport}: {e}")
        # Other errors are expected and okay

    # Subsequent echo should still succeed, proving session survived
    try:
        echo_res = await client.run_tool("echo", {"message": "after-error"})
        assert "after-error" in str(echo_res).lower(), f"Session did not survive error on {transport}"
    except Exception as e:
        pytest.fail(f"Session did not survive error on {transport}: {e}")


async def test_invalid_tool_name(mcp_client):
    """Test handling of invalid tool names."""
    transport, client = mcp_client

    try:
        await client.run_tool("nonexistent_tool_12345", {})
        pytest.fail(f"Expected exception for nonexistent tool on {transport}")
    except Exception as e:
        # Should get some kind of error for invalid tool
        error_msg = str(e).lower()
        expected_words = ["not found", "unknown", "invalid", "tool", "error"]
        assert any(word in error_msg for word in expected_words), (
            f"Unexpected error message format for {transport}: {e}"
        )


@pytest.mark.xfail(reason="ExceptionGroup wrapping in Python 3.11+ hides actual MCP error message")
async def test_invalid_parameters(mcp_client):
    """Test handling of invalid parameters for valid tools."""
    transport, client = mcp_client

    try:
        # Try to call add_numbers with invalid parameter names
        await client.run_tool("add_numbers", {"x": 1, "y": 2})  # Wrong parameter names (should be 'a' and 'b')
        # Some implementations might be lenient or have parameter mapping, so we don't automatically fail
    except Exception as e:
        # If it fails, that's also acceptable behavior - check error message makes sense
        error_msg = str(e).lower()
        expected_words = ["parameter", "validation", "schema", "argument", "invalid", "required"]
        if not any(word in error_msg for word in expected_words):
            pytest.fail(f"Unexpected error message for invalid parameters on {transport}: {e}")


@pytest.mark.xfail(reason="ExceptionGroup wrapping in Python 3.11+ hides actual MCP error message")
async def test_missing_required_parameters(mcp_client):
    """Test handling of missing required parameters."""
    transport, client = mcp_client

    try:
        # Try to call add_numbers without any parameters
        await client.run_tool("add_numbers", {})
        pytest.fail(f"Expected exception for missing required parameters on {transport}")
    except Exception as e:
        error_msg = str(e).lower()
        # Should indicate missing/required parameter error
        expected_words = ["required", "missing", "parameter", "validation", "argument"]
        assert any(word in error_msg for word in expected_words), (
            f"Unexpected error message for missing params on {transport}: {e}"
        )


@pytest.mark.xfail(reason="ExceptionGroup wrapping in Python 3.11+ hides actual MCP error message")
async def test_malformed_arguments(mcp_client):
    """Test handling of malformed argument types."""
    transport, client = mcp_client

    try:
        # Try to call add_numbers with string instead of numbers
        await client.run_tool("add_numbers", {"a": "not_a_number", "b": "also_not_a_number"})
        # Some implementations might handle type coercion, so we don't automatically fail
    except Exception as e:
        # If it fails, check that the error message is reasonable
        error_msg = str(e).lower()
        expected_words = ["type", "validation", "invalid", "number", "parameter", "schema"]
        if not any(word in error_msg for word in expected_words):
            pytest.fail(f"Unexpected error message for type mismatch on {transport}: {e}")


async def test_client_state_after_error(mcp_client):
    """Test that client remains in a good state after various errors."""
    transport, client = mcp_client

    # Verify client is initially connected
    assert client._connected, f"Client should be connected initially on {transport}"

    # Try various error scenarios
    error_scenarios = [
        ("nonexistent_tool", {}),
        ("add_numbers", {}),  # Missing params
        ("echo", {"wrong_param": "value"}),  # Wrong param name
    ]

    for tool_name, params in error_scenarios:
        try:
            await client.run_tool(tool_name, params)
        except Exception:
            # Errors are expected, just continue
            pass

        # Client should still be connected after each error
        assert client._connected, f"Client should remain connected after error with {tool_name} on {transport}"

    # Final test - client should still work for valid operations
    try:
        result = await client.run_tool("echo", {"message": "still_working"})
        assert "still_working" in str(result).lower(), f"Client not functional after errors on {transport}"
    except Exception as e:
        pytest.fail(f"Client not functional after error scenarios on {transport}: {e}")

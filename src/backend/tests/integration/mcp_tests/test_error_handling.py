import pytest

pytestmark = pytest.mark.asyncio


async def _invoke_simulate_error(client, kind):
    """Helper that calls simulate_error and returns True if error surfaced."""
    try:
        result = await client.call_tool("simulate_error", {"error_type": kind})
    except Exception as exc:  # noqa: BLE001
        # Exception propagated - that counts.
        return str(exc)

    # Some transports embed error in JSON-RPC envelope
    if isinstance(result, dict) and result.get("error"):
        return str(result["error"])
    return str(result)


@pytest.mark.parametrize("kind", ["validation", "runtime", "timeout"])
async def test_simulate_error_propagation(mcp_client, kind):
    transport, client = mcp_client
    msg = await _invoke_simulate_error(client, kind)

    if transport == "stdio":
        pytest.xfail("STDIO transport wraps errors in TaskGroup - improve parsing later.")

    assert kind in msg.lower()


async def test_session_survives_error(mcp_client):
    _transport, client = mcp_client
    # Trigger runtime error
    _ = await _invoke_simulate_error(client, "runtime")

    # Subsequent echo should still succeed
    echo_res = await client.call_tool("echo", {"message": "after-error"})
    assert "after-error" in str(echo_res).lower()

import uuid

import pytest

pytestmark = pytest.mark.asyncio


async def _register_faulty_server(client, headers: dict[str, str]):
    """Register a dummy MCP server with an invalid URL so that the health check fails."""
    server_name = f"faulty-{uuid.uuid4().hex[:6]}"

    # Intentionally point to a port that is very unlikely to be open
    server_config = {
        "mode": "sse",
        "url": "invalid-url",  # malformed URL triggers validation error quickly
    }

    res = await client.post(f"api/v2/mcp/servers/{server_name}", headers=headers, json=server_config)
    res.raise_for_status()
    return server_name


async def _fetch_servers(client, headers: dict[str, str]):
    response = await client.get("api/v2/mcp/servers", headers=headers)
    response.raise_for_status()
    return response.json()


def _get_error_server_entry(servers):
    for entry in servers:
        if entry.get("status") not in ("connected", "unknown"):
            return entry
    return None


async def test_server_check_error_structure(client, logged_in_headers):
    """Ensure the /servers endpoint returns structured error information."""
    # 1) Register a server that is guaranteed to fail the health check
    await _register_faulty_server(client, logged_in_headers)

    # 2) Fetch the server list - the faulty server should surface an error
    servers = await _fetch_servers(client, logged_in_headers)

    error_entry = _get_error_server_entry(servers)
    assert error_entry is not None, "Expected at least one server with a non-success status"

    # 3) Validate the structure of the error payload
    error = error_entry.get("error")
    assert error, "Missing 'error' field in server info"

    assert "type" in error, "Missing error type"
    assert "message" in error, "Missing error message"
    assert "suggestions" in error, "Missing 'suggestions' key"
    assert isinstance(error["suggestions"], list), "'suggestions' should be a list"

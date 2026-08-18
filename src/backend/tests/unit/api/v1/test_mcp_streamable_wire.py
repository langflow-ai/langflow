"""Wire-level test for /api/v1/mcp/streamable.

The existing coverage in ``test_mcp.py`` mocks ``StreamableHTTPSessionManager``
and asserts ``handle_request`` was called, which passes whether or not the
server can actually speak MCP. This posts real JSON-RPC through ASGI with the
session manager left alone, so it fails if the server stops answering.

Raw JSON-RPC rather than an SDK client, so that an SDK API change does not
force this harness to be rewritten alongside the code it guards.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from httpx import AsyncClient

PROTOCOL_VERSION = "2025-06-18"
MCP_ACCEPT = "application/json, text/event-stream"


def _decode(response) -> dict:
    """Read one JSON-RPC message out of either a JSON or an SSE response."""
    content_type = response.headers.get("content-type", "")
    body = response.text

    if content_type.startswith("application/json"):
        return json.loads(body)

    if content_type.startswith("text/event-stream"):
        for line in body.splitlines():
            if line.startswith("data:"):
                return json.loads(line[len("data:") :].strip())
        msg = f"no data frame in SSE response: {body!r}"
        raise AssertionError(msg)

    msg = f"unexpected content-type {content_type!r}, body: {body[:400]!r}"
    raise AssertionError(msg)


async def _post(client: AsyncClient, headers: dict, payload: dict):
    return await client.post(
        "api/v1/mcp/streamable",
        headers={**headers, "Accept": MCP_ACCEPT, "Content-Type": "application/json"},
        json=payload,
    )


@pytest.mark.asyncio
async def test_streamable_endpoint_answers_initialize_over_the_wire(client: AsyncClient, logged_in_headers):
    """A real initialize must come back as a real MCP result, not just a 200."""
    response = await _post(
        client,
        logged_in_headers,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "langflow-wire-test", "version": "0"},
            },
        },
    )

    assert response.status_code == 200, response.text
    message = _decode(response)

    assert message.get("jsonrpc") == "2.0"
    assert "result" in message, f"initialize returned an error: {message}"
    assert message["result"]["protocolVersion"]
    assert message["result"]["serverInfo"]["name"]


@pytest.mark.asyncio
async def test_streamable_endpoint_requires_auth(client: AsyncClient):
    """Unauthenticated JSON-RPC must not reach the MCP server."""
    response = await client.post(
        "api/v1/mcp/streamable",
        headers={"Accept": MCP_ACCEPT},
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
    )
    assert response.status_code == 403

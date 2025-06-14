import asyncio

import pytest
from langflow.base.mcp.sse_client import MCPSseClient

pytestmark = pytest.mark.asyncio


async def test_protocol_info_metadata(mcp_client):
    transport, client = mcp_client

    info = client.get_protocol_info()

    assert info["transport_type"] in {"streamable_http", "http_sse", "stdio"}
    if transport == "sse":
        assert info["transport_type"] in {"streamable_http", "http_sse"}
        assert info["protocol_version"] in {"2025-03-26", "2024-11-05"}
    else:
        assert info["transport_type"] == "stdio"
        # stdio protocol_version may be "stdio" or None
        assert info["protocol_version"] in {"stdio", None}


async def test_sse_discovery_task_cleanup(sse_reference_server):
    client = MCPSseClient()
    await client.connect_to_server(sse_reference_server)

    # Snapshot tasks before disconnect (keep local reference for clarity)
    _ = client.discovery_task

    before = {t for t in asyncio.all_tasks() if not t.done()}

    await client.disconnect()
    await asyncio.sleep(0.05)  # allow cancellations to propagate

    # Ensure client cleared state
    assert client.discovery_task is None

    after = {t for t in asyncio.all_tasks() if not t.done()}

    # No additional pending tasks; after subset of before
    assert after.issubset(before)

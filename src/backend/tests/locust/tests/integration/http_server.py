"""Real localhost ASGI serve for concurrent HTTP clients (SSE / MCP)."""

from __future__ import annotations

import asyncio
import socket
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import pytest
import uvicorn
from httpx import ASGITransport

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from httpx import AsyncClient


def _asgi_app(client: AsyncClient):
    transport = client._transport
    if isinstance(transport, ASGITransport):
        return transport.app
    msg = f"client transport is not ASGITransport: {type(transport)!r}"
    raise TypeError(msg)


@asynccontextmanager
async def real_http_base_url(client: AsyncClient) -> AsyncIterator[str]:
    """Serve the test app on a real localhost port (lifespan already started).

    Required for concurrent HTTP SSE subscribe + POST, and for the MCP SDK
    streamable-http client which needs a real URL.
    """
    app = _asgi_app(client)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        lifespan="off",
        access_log=False,
    )
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    try:
        for _ in range(200):
            if server.started:
                break
            await asyncio.sleep(0.01)
        else:
            pytest.fail("uvicorn failed to start for real HTTP coverage")
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        await asyncio.wait_for(task, timeout=30.0)

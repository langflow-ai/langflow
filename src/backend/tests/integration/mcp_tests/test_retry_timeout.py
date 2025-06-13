# ruff: noqa: S603, ASYNC220

import asyncio
import socket
import subprocess

import pytest
from langflow.base.mcp.sse_client import MCPSseClient

from .conftest import (
    REFERENCE_IMPL_DIR,
    SSE_SERVER_SCRIPT,
    _require_executable,
    _wait_for_http_health,
)  # type: ignore[import-not-found]

pytestmark = pytest.mark.asyncio


def _free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


async def _delayed_start_server(port: int, delay: float):
    """Spawn the reference SSE server after *delay* seconds and return the Popen."""
    await asyncio.sleep(delay)
    node_cmd = _require_executable("node")
    proc = subprocess.Popen(
        [node_cmd, str(SSE_SERVER_SCRIPT), str(port)],
        cwd=str(REFERENCE_IMPL_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    # Wait for health ready
    _wait_for_http_health(f"http://127.0.0.1:{port}/health", timeout=10)
    return proc


@pytest.mark.usefixtures("event_loop")
async def test_connect_with_retry_success_on_second_attempt():
    port = _free_port()
    url = f"http://127.0.0.1:{port}/mcp"

    # Schedule server start after 0.5s
    server_task = asyncio.create_task(_delayed_start_server(port, 0.5))

    client = MCPSseClient()
    client.base_retry_delay = 0.2  # quick yet gives room

    try:
        tools = await client.connect_to_server_with_retry(url, max_retries=6)
        names = [t.name for t in tools]
        assert "echo" in names
    finally:
        await client.disconnect()
        proc = await server_task
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

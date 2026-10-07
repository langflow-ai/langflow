"""A pooled Streamable HTTP session must not outlive the server it talks to.

Drives a real MCP server over real HTTP: the server restarts, which drops every
session it knew, and the next listing or tool call has to start a new one
instead of failing on the pooled session.
"""

import asyncio
import socket
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

pytest.importorskip("mcp")

from lfx.base.mcp.util import MCPSessionManager, MCPStreamableHttpClient

SERVER = """
import os
import sys

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("restartable-server", host="127.0.0.1", port=int(sys.argv[1]))


@mcp.tool()
def pid() -> str:
    return str(os.getpid())


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
"""


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


async def _wait_until_listening(port: int) -> None:
    for _ in range(100):
        try:
            _, writer = await asyncio.open_connection("127.0.0.1", port)
        except OSError:
            await asyncio.sleep(0.1)
        else:
            writer.close()
            await writer.wait_closed()
            return
    msg = f"MCP server did not start on port {port}"
    raise TimeoutError(msg)


class _Server:
    def __init__(self, script: Path, port: int) -> None:
        self._args = [sys.executable, str(script), str(port)]
        self.port = port
        self._process: subprocess.Popen | None = None

    async def start(self) -> None:
        self._process = subprocess.Popen(self._args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)  # noqa: ASYNC220, S603
        await _wait_until_listening(self.port)

    def stop(self) -> None:
        if self._process and self._process.poll() is None:
            self._process.kill()
            self._process.wait(timeout=10)


@pytest.fixture
def server(tmp_path: Path) -> Iterator[_Server]:
    script = tmp_path / "restartable_server.py"
    script.write_text(SERVER, encoding="utf-8")
    running = _Server(script, _free_port())
    yield running
    running.stop()


@pytest.fixture
async def manager():
    session_manager = MCPSessionManager()
    yield session_manager
    await session_manager.cleanup_all()


def _client(manager: MCPSessionManager) -> MCPStreamableHttpClient:
    client = MCPStreamableHttpClient(tool_execution_timeout=30)
    client._get_session_manager = lambda: manager  # type: ignore[method-assign]
    return client


async def _restart(server: _Server) -> None:
    server.stop()
    await server.start()


async def test_should_start_a_new_session_when_connecting_after_the_server_restarted(manager, server):
    await server.start()
    url = f"http://127.0.0.1:{server.port}/mcp"
    first = _client(manager)
    await first._connect_to_server(url)
    first.set_session_context("chat_server")
    old_pid = (await first.run_tool("pid", {})).content[0].text
    await _restart(server)

    second = _client(manager)
    tools = await second._connect_to_server(url)
    second.set_session_context("chat_server")

    assert [tool.name for tool in tools] == ["pid"]
    assert (await second.run_tool("pid", {})).content[0].text != old_pid


async def test_should_recover_tool_call_when_the_server_restarted(manager, server):
    await server.start()
    url = f"http://127.0.0.1:{server.port}/mcp"
    client = _client(manager)
    await client._connect_to_server(url)
    client.set_session_context("chat_server")
    old_pid = (await client.run_tool("pid", {})).content[0].text
    await _restart(server)

    result = await client.run_tool("pid", {})

    assert result.content[0].text != old_pid

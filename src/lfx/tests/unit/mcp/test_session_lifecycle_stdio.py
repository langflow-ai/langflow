"""Session ownership against a real MCP server over real stdio.

These follow the order the MCP Tools component uses: connect first, which binds
a generated context, then set the run's context, then call tools. Each case
checks the subprocess itself, not only the manager's bookkeeping.
"""

import asyncio
import os
import shlex
import signal
import sys
from pathlib import Path

import pytest

pytest.importorskip("mcp")

from lfx.base.mcp.util import MCPSessionManager, MCPStdioClient

SERVER = """
import asyncio
import os

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("lifecycle-server")


@mcp.tool()
async def echo(value: str) -> str:
    return value


@mcp.tool()
def pid() -> str:
    return str(os.getpid())


@mcp.tool()
async def slow_echo(value: str) -> str:
    await asyncio.sleep(float(os.environ.get("SLOW_DELAY", "1")))
    return value


if __name__ == "__main__":
    mcp.run()
"""


@pytest.fixture
def server_command(tmp_path: Path) -> str:
    server = tmp_path / "lifecycle_server.py"
    server.write_text(SERVER, encoding="utf-8")
    return shlex.join([sys.executable, str(server)])


@pytest.fixture
async def manager():
    session_manager = MCPSessionManager()
    yield session_manager
    await session_manager.cleanup_all()


def _client(manager: MCPSessionManager) -> MCPStdioClient:
    client = MCPStdioClient(tool_execution_timeout=30)
    client._get_session_manager = lambda: manager  # type: ignore[method-assign]
    return client


def _session_tasks(manager: MCPSessionManager) -> list[asyncio.Task]:
    return [info["task"] for key in list(manager.sessions_by_server) for info in manager._sessions_for(key).values()]


async def test_should_release_subprocess_when_context_is_set_after_connecting(manager, server_command):
    client = _client(manager)
    await client._connect_to_server(server_command)
    client.set_session_context("run-session_lifecycle")
    for value in ("a", "b", "c"):
        await client.run_tool("echo", {"value": value})
    [task] = _session_tasks(manager)

    await client.disconnect()
    await asyncio.sleep(0)

    assert manager._session_refcount == {}
    assert manager._context_to_session == {}
    assert _session_tasks(manager) == []
    assert task.done()


async def _connected(manager: MCPSessionManager, command: str, delay: str, *, context_first: bool) -> MCPStdioClient:
    client = _client(manager)
    if context_first:
        client.set_session_context("shared-context")
    await client._connect_to_server(command, env={"SLOW_DELAY": delay})
    client.set_session_context("shared-context")
    return client


@pytest.mark.parametrize("context_first", [True, False], ids=["context-then-connect", "connect-then-context"])
async def test_should_finish_in_flight_call_when_context_binds_another_server(manager, server_command, context_first):
    first = await _connected(manager, server_command, "5", context_first=context_first)
    in_flight = asyncio.create_task(first.run_tool("slow_echo", {"value": "kept"}))
    await asyncio.sleep(0.3)

    # Same context, other server key: concurrent runs of one chat session whose
    # headers resolve to different values do this.
    second = await _connected(manager, server_command, "2", context_first=context_first)
    await second.run_tool("echo", {"value": "other"})

    result = await asyncio.wait_for(in_flight, timeout=15)

    assert result.content[0].text == "kept"
    assert len(_session_tasks(manager)) == 2

    await first.disconnect()
    await second.disconnect()
    await asyncio.sleep(0)

    assert manager._session_refcount == {}
    assert _session_tasks(manager) == []


async def _server_pid(client: MCPStdioClient) -> int:
    result = await client.run_tool("pid", {})
    return int(result.content[0].text)


async def _kill(pid: int) -> None:
    os.kill(pid, signal.SIGKILL if hasattr(signal, "SIGKILL") else signal.SIGTERM)
    await asyncio.sleep(0.5)


async def test_should_start_a_new_server_when_connecting_after_the_process_died(manager, server_command):
    first = _client(manager)
    await first._connect_to_server(server_command)
    first.set_session_context("chat_server")
    dead_pid = await _server_pid(first)
    await _kill(dead_pid)

    # The next run of the flow lists the tools again before calling one.
    second = _client(manager)
    tools = await second._connect_to_server(server_command)
    second.set_session_context("chat_server")

    assert {tool.name for tool in tools} >= {"echo", "pid"}
    assert await _server_pid(second) != dead_pid


async def test_should_recover_tool_call_when_the_dead_process_was_shared(manager, server_command):
    first = _client(manager)
    first.set_session_context("chat-1_server")
    await first._connect_to_server(server_command)
    second = _client(manager)
    second.set_session_context("chat-2_server")
    await second._connect_to_server(server_command)
    dead_pid = await _server_pid(first)
    assert await _server_pid(second) == dead_pid
    await _kill(dead_pid)

    result = await first.run_tool("echo", {"value": "after-crash"})

    assert result.content[0].text == "after-crash"
    assert await _server_pid(second) != dead_pid


async def test_should_finish_call_on_new_process_when_another_run_discards_the_dead_one(manager, server_command):
    first = _client(manager)
    first.set_session_context("chat-1_server")
    await first._connect_to_server(server_command)
    second = _client(manager)
    second.set_session_context("chat-2_server")
    await second._connect_to_server(server_command)
    dead_pid = await _server_pid(first)
    await _kill(dead_pid)
    # The second run fetched the pooled session before the first one replaced it.
    stale = await second._get_or_create_session()
    assert await _server_pid(first) != dead_pid
    in_flight = asyncio.create_task(first.run_tool("slow_echo", {"value": "kept"}))
    await asyncio.sleep(0.3)

    # Its call on that session fails now, and it discards the session.
    await second._discard_dead_session(stale)

    result = await asyncio.wait_for(in_flight, timeout=10)
    assert result.content[0].text == "kept"

"""An idle sweep must not dispose of a session with requests still in flight."""

import asyncio
import contextlib
import shlex
import socket
import subprocess
import sys
from pathlib import Path

import pytest
from anyio import fail_after

pytest.importorskip("mcp")

from lfx.base.mcp.util import MCPSessionManager, MCPStdioClient, MCPStreamableHttpClient
from lfx.services.deps import get_settings_service

SERVER = """
import asyncio
import sys
from pathlib import Path
from mcp import types
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("idle-activity-server", host="127.0.0.1", port=int(sys.argv[2]))

@mcp.tool()
async def wait_for_release(ledger: str, gate: str, value: str) -> str:
    with Path(ledger).open("a", encoding="utf-8") as output:
        output.write(value + "\\n")
    while not Path(gate).exists():
        await asyncio.sleep(0.02)
    return value

original_listing = mcp._mcp_server.request_handlers[types.ListToolsRequest]

async def slow_listing(request):
    block = Path(__file__).parent / "block-listing"
    if block.exists():
        (block.parent / "listing-started").touch()
        while block.exists():
            await asyncio.sleep(0.02)
    return await original_listing(request)

mcp._mcp_server.request_handlers[types.ListToolsRequest] = slow_listing

if __name__ == "__main__":
    mcp.run(transport=sys.argv[1])
"""


async def _wait_for_calls(ledger: Path, count: int) -> None:
    with fail_after(15):
        # The subprocess records its start in a file; an asyncio.Event cannot
        # observe this cross-process signal.
        while not ledger.exists() or len(ledger.read_text(encoding="utf-8").splitlines()) < count:  # noqa: ASYNC110
            await asyncio.sleep(0.02)


def _session_info(manager: MCPSessionManager) -> dict:
    [info] = [info for key in manager.sessions_by_server for info in manager._sessions_for(key).values()]
    return info


@pytest.fixture(params=["stdio", "streamable-http"])
async def connection(request, tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings_service().settings, "mcp_session_idle_timeout", 1)
    server = tmp_path / "idle_server.py"
    server.write_text(SERVER, encoding="utf-8")
    manager = MCPSessionManager()
    process = None
    client = MCPStdioClient(tool_execution_timeout=10)
    client._get_session_manager = lambda: manager  # type: ignore[method-assign]
    try:
        if request.param == "stdio":
            await client._connect_to_server(shlex.join([sys.executable, str(server), "stdio", "0"]))
        else:
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            process = subprocess.Popen(  # noqa: ASYNC220, S603
                [sys.executable, str(server), "streamable-http", str(port)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            with fail_after(15):
                while True:
                    try:
                        _, writer = await asyncio.open_connection("127.0.0.1", port)
                    except OSError:
                        await asyncio.sleep(0.1)
                    else:
                        writer.close()
                        await writer.wait_closed()
                        break
            client = MCPStreamableHttpClient(tool_execution_timeout=10)
            client._get_session_manager = lambda: manager  # type: ignore[method-assign]
            await client._connect_to_server(f"http://127.0.0.1:{port}/mcp")
        client.set_session_context("idle-activity-run")
        yield manager, client
    finally:
        await client.disconnect()
        await manager.cleanup_all()
        if process and process.poll() is None:
            process.kill()
            process.wait(timeout=10)


async def test_should_finish_tool_once_when_idle_sweep_runs_during_execution(connection, tmp_path):
    manager, client = connection
    ledger, gate = tmp_path / "calls.txt", tmp_path / "release"
    pending = asyncio.create_task(
        client.run_tool("wait_for_release", {"ledger": str(ledger), "gate": str(gate), "value": "record"})
    )
    try:
        await _wait_for_calls(ledger, 1)
        transport = _session_info(manager)["task"]
        await asyncio.sleep(1.1)
        await manager._cleanup_idle_sessions()
        assert not transport.done()
        gate.touch()
        result = await asyncio.wait_for(pending, timeout=10)
        assert result.content[0].text == "record"
        assert ledger.read_text(encoding="utf-8").splitlines() == ["record"]

        # The idle interval starts at completion, not at request acquisition.
        await manager._cleanup_idle_sessions()
        assert not transport.done()
        await asyncio.sleep(1.1)
        await manager._cleanup_idle_sessions()
        assert transport.done()
        assert manager._context_to_session == {}
    finally:
        pending.cancel()
        with contextlib.suppress(asyncio.CancelledError, ValueError):
            await pending


async def test_should_finish_tool_listing_when_idle_sweep_runs_during_discovery(connection, tmp_path):
    manager, client = connection
    block = tmp_path / "block-listing"
    started = tmp_path / "listing-started"
    block.touch()
    pending = asyncio.create_task(client._list_tools())
    try:
        with fail_after(15):
            while not started.exists():  # noqa: ASYNC110
                await asyncio.sleep(0.02)
        transport = _session_info(manager)["task"]
        await asyncio.sleep(1.1)
        await manager._cleanup_idle_sessions()
        assert not transport.done()
        block.unlink()
        assert [tool.name for tool in await asyncio.wait_for(pending, timeout=10)] == ["wait_for_release"]
    finally:
        pending.cancel()
        with contextlib.suppress(asyncio.CancelledError, ValueError):
            await pending


async def test_should_keep_shared_session_when_one_of_two_active_calls_is_cancelled(connection, tmp_path):
    manager, client = connection
    ledger, gate = tmp_path / "calls.txt", tmp_path / "release"
    pending = [
        asyncio.create_task(
            client.run_tool("wait_for_release", {"ledger": str(ledger), "gate": str(gate), "value": value})
        )
        for value in ("cancelled", "kept")
    ]
    try:
        await _wait_for_calls(ledger, 2)
        transport = _session_info(manager)["task"]
        pending[0].cancel()
        with pytest.raises(asyncio.CancelledError):
            await pending[0]
        await asyncio.sleep(1.1)
        await manager._cleanup_idle_sessions()
        assert not transport.done()
        gate.touch()
        assert (await asyncio.wait_for(pending[1], timeout=10)).content[0].text == "kept"
        assert sorted(ledger.read_text(encoding="utf-8").splitlines()) == ["cancelled", "kept"]
    finally:
        for task in pending:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, ValueError):
                await task


@pytest.mark.parametrize("ending", ["cancel", "timeout"])
async def test_should_reap_session_after_request_is_cancelled_or_times_out(connection, tmp_path, ending):
    manager, client = connection
    ledger, gate = tmp_path / "calls.txt", tmp_path / "release"
    pending = asyncio.create_task(
        client.run_tool("wait_for_release", {"ledger": str(ledger), "gate": str(gate), "value": "record"}, timeout=3)
    )
    try:
        await _wait_for_calls(ledger, 1)
        transport = _session_info(manager)["task"]
        if ending == "cancel":
            pending.cancel()
            with pytest.raises(asyncio.CancelledError):
                await pending
        else:
            with pytest.raises(ValueError, match="timed out"):
                await asyncio.wait_for(pending, timeout=10)
        await asyncio.sleep(1.1)
        await manager._cleanup_idle_sessions()
        assert transport.done()
        assert manager._context_to_session == {}
        assert ledger.read_text(encoding="utf-8").splitlines() == ["record"]
    finally:
        pending.cancel()
        with contextlib.suppress(asyncio.CancelledError, ValueError):
            await pending

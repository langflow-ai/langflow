"""Wire-level test for the agentic MCP server over stdio.

Everything else that covers this server calls the decorated functions in-process,
so it proves the Python is importable and nothing about the server actually
speaking MCP. This drives ``python -m langflow.agentic.mcp`` as a real
subprocess and talks newline-delimited JSON-RPC to it directly.

Deliberately no SDK client. The point is to depend on the wire format rather
than on ``ClientSession``, so an SDK API change does not force this harness to
be rewritten in the same PR as the code it is meant to guard. The one part that
does track the protocol is the ``initialize`` handshake in ``_handshake``.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

import pytest

# Booting the server imports the whole langflow service stack. Measured at ~3.5s.
# Both ceilings stay under pytest-timeout's global 90s (pyproject.toml), which
# uses timeout_method="thread" and would os._exit the run rather than let this
# harness report which call hung.
STARTUP_TIMEOUT = 45.0
CALL_TIMEOUT = 30.0
PROTOCOL_VERSION = "2025-06-18"


class _StdioPeer:
    """Newline-delimited JSON-RPC over a subprocess's stdin/stdout."""

    def __init__(self, proc: asyncio.subprocess.Process) -> None:
        self._proc = proc
        self._next_id = 0
        self._stderr = bytearray()
        # Drain stderr continuously. The pipe holds 64KB, and a subprocess that
        # fills it blocks on write, which would deadlock the request loop.
        self._stderr_task = asyncio.create_task(self._drain_stderr())

    async def _drain_stderr(self) -> None:
        while True:
            chunk = await self._proc.stderr.read(4096)
            if not chunk:
                return
            self._stderr.extend(chunk)

    @property
    def stderr_text(self) -> str:
        return self._stderr.decode(errors="replace")

    async def _send(self, payload: dict) -> None:
        self._proc.stdin.write((json.dumps(payload) + "\n").encode())
        await self._proc.stdin.drain()

    async def notify(self, method: str, params: dict | None = None) -> None:
        await self._send({"jsonrpc": "2.0", "method": method, "params": params or {}})

    async def request(self, method: str, params: dict | None = None, *, timeout: float = CALL_TIMEOUT) -> dict:
        self._next_id += 1
        request_id = self._next_id
        await self._send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}})

        async def _read_matching() -> dict:
            while True:
                line = await self._proc.stdout.readline()
                if not line:
                    msg = f"server closed stdout before answering {method}; stderr:\n{self.stderr_text}"
                    raise AssertionError(msg)
                try:
                    message = json.loads(line)
                except json.JSONDecodeError:
                    # Anything that is not JSON on stdout is a framing bug: stdout
                    # is the JSON-RPC channel and logs belong on stderr.
                    msg = f"non-JSON line on the JSON-RPC channel: {line!r}"
                    raise AssertionError(msg) from None
                if message.get("id") == request_id:
                    return message

        return await asyncio.wait_for(_read_matching(), timeout=timeout)


async def _handshake(peer: _StdioPeer) -> dict:
    """Run the MCP initialize handshake. This is the part protocol 2026-07-28 removes."""
    response = await peer.request(
        "initialize",
        {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "langflow-wire-test", "version": "0"},
        },
        timeout=STARTUP_TIMEOUT,
    )
    await peer.notify("notifications/initialized")
    return response


@pytest.fixture
async def server():
    env = {
        **os.environ,
        "LANGFLOW_AUTO_LOGIN": "true",
        # Keep the subprocess off any real user database.
        "LANGFLOW_DATABASE_URL": "sqlite:///:memory:",
    }
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "langflow.agentic.mcp",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    try:
        yield proc
    finally:
        if proc.returncode is None:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=15)
            except TimeoutError:
                proc.kill()
                await proc.wait()


async def test_stdio_server_completes_handshake_and_lists_tools(server):
    """The server must answer initialize and tools/list over a real pipe."""
    peer = _StdioPeer(server)

    init = await _handshake(peer)
    assert "result" in init, f"initialize failed: {init}"
    assert init["result"]["protocolVersion"]
    assert init["result"]["serverInfo"]["name"] == "langflow-agentic"

    listed = await peer.request("tools/list")
    assert "result" in listed, f"tools/list failed: {listed}"

    tools = listed["result"]["tools"]
    assert tools, "server advertised no tools"

    names = {tool["name"] for tool in tools}
    assert "run_assistant" in names, f"run_assistant missing from {sorted(names)}"

    # Every advertised tool must carry a usable input schema. This is the read
    # that silently returns nothing if the wire model's field name changes.
    for tool in tools:
        assert tool.get("inputSchema"), f"{tool['name']} advertised no inputSchema"
        assert tool["inputSchema"].get("type") == "object", f"{tool['name']} inputSchema is not an object schema"


async def test_stdio_server_rejects_unknown_tool_over_the_wire(server):
    """An unknown tool must come back as a JSON-RPC answer, not kill the process.

    Exercises the tools/call path end to end without depending on any real
    assistant run, which would need model credentials.
    """
    peer = _StdioPeer(server)
    await _handshake(peer)

    response = await peer.request(
        "tools/call",
        {"name": "definitely_not_a_real_tool", "arguments": {}},
    )

    # Either a JSON-RPC error or an isError result is a correct answer. Silence,
    # a crash, or a success is not.
    assert "error" in response or response.get("result", {}).get("isError") is True, (
        f"unknown tool was not reported as a failure: {response}"
    )

    # The server must still be alive and answering afterwards.
    listed = await peer.request("tools/list")
    assert "result" in listed

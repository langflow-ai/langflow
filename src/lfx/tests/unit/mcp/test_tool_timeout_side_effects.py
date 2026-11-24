"""A tool call that times out must not be sent again.

A timeout says nothing about whether the server ran the tool: it may have
written the record and only its answer was late. This drives a real MCP server
over real stdio, whose tool records every invocation before answering, and
checks that one timed-out call leaves exactly one side effect behind.
"""

import sys
from pathlib import Path

import pytest

pytest.importorskip("mcp")

from lfx.base.mcp.util import MCPSessionManager, MCPStdioClient
from mcp import StdioServerParameters

SERVER = """
import asyncio
import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

LEDGER = Path(os.environ["LEDGER_PATH"])
mcp = FastMCP("ledger-server")


@mcp.tool()
async def create_record(value: str) -> str:
    with LEDGER.open("a", encoding="utf-8") as ledger:
        ledger.write(value + "\\n")
    await asyncio.Event().wait()
    return "recorded"


if __name__ == "__main__":
    mcp.run()
"""


@pytest.mark.asyncio
async def test_should_leave_one_side_effect_when_tool_call_times_out(tmp_path: Path):
    server = tmp_path / "ledger_server.py"
    server.write_text(SERVER, encoding="utf-8")
    ledger = tmp_path / "ledger.txt"
    manager = MCPSessionManager()
    # Generous: the record must be written before the timeout even on a
    # loaded runner. The tool never answers, so the call always times out.
    client = MCPStdioClient(tool_execution_timeout=5.0)
    client._get_session_manager = lambda: manager  # type: ignore[method-assign]
    client._connection_params = StdioServerParameters(
        command=sys.executable,
        args=[str(server)],
        env={"LEDGER_PATH": str(ledger)},
    )
    client._connected = True
    client.set_session_context("ledger-ctx")

    try:
        with pytest.raises(ValueError, match="timed out"):
            await client.run_tool("create_record", {"value": "payment-1"})
    finally:
        await manager.cleanup_all()

    assert ledger.read_text(encoding="utf-8").splitlines() == ["payment-1"]

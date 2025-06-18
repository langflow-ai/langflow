import contextlib
import shutil
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from langflow.base.mcp.util import MCPSseClient, MCPStdioClient

# ----------------------------------------------------------------------------
# Paths
# ----------------------------------------------------------------------------
TESTS_DIR = Path(__file__).parent
REFERENCE_IMPL_DIR = TESTS_DIR / "reference_implementation"
SSE_SERVER_SCRIPT = REFERENCE_IMPL_DIR / "mcp_sse_reference.js"
STDIO_SERVER_SCRIPT = REFERENCE_IMPL_DIR / "mcp_stdio_reference.js"


# ----------------------------------------------------------------------------
# Utility helpers
# ----------------------------------------------------------------------------


def _require_executable(name: str) -> str:
    """Return the path to *name* if it exists in $PATH else skip the caller test."""
    path = shutil.which(name)
    if path is None:
        pytest.skip(f"'{name}' executable not found - skipping MCP integration tests")
    return path


def _get_free_tcp_port() -> int:
    """Return an available TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def _wait_for_http_health(url: str, timeout: float = 10.0) -> None:
    """Block until GET *url* returns HTTP 200 or *timeout* seconds elapse."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            r = httpx.get(url, timeout=1.0)
            if r.status_code == 200:
                return
        except httpx.HTTPError:
            # Connection not yet accepting; retry until deadline
            pass
        time.sleep(0.1)
    msg = f"Timed out waiting for server health at {url}"
    raise RuntimeError(msg)


# ----------------------------------------------------------------------------
# Session-scoped fixture spinning up the unified SSE/Streamable HTTP server
# ----------------------------------------------------------------------------


@pytest.fixture(scope="session")
def sse_reference_server() -> Iterator[str]:
    """Launch the reference *mcp_sse_reference.js* server on a dynamic port.

    Yields the SSE endpoint URL to connect to.
    The process is terminated after the test session.
    """
    node_cmd = _require_executable("node")

    if not SSE_SERVER_SCRIPT.exists():
        pytest.skip("Reference SSE server script not found - skipping MCP integration tests")

    port = _get_free_tcp_port()

    # Ensure Node resolves ESM imports relative to the reference directory
    proc = subprocess.Popen(  # noqa: S603
        [node_cmd, str(SSE_SERVER_SCRIPT), str(port)],
        cwd=str(REFERENCE_IMPL_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        _wait_for_http_health(f"http://127.0.0.1:{port}/health", timeout=20.0)
    except Exception:  # noqa: BLE001
        # If startup failed, stream logs for easier debugging before skipping
        stdout, stderr = proc.communicate(timeout=1)
        sys.stderr.write("--- reference SSE server stdout ---\n")
        sys.stderr.write(stdout)
        sys.stderr.write("--- reference SSE server stderr ---\n")
        sys.stderr.write(stderr)
        proc.kill()
        pytest.skip("Unable to start reference SSE server - see logs above")

    # Return the /sse endpoint for SSE connections
    sse_url = f"http://127.0.0.1:{port}/sse"
    yield sse_url

    # Teardown - terminate process
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


# ----------------------------------------------------------------------------
# Fixture returning the command string for the STDIO reference server
# ----------------------------------------------------------------------------


@pytest.fixture(scope="session")
def stdio_reference_command() -> str:
    node_cmd = _require_executable("node")
    if not STDIO_SERVER_SCRIPT.exists():
        pytest.skip("Reference STDIO server script not found - skipping MCP integration tests")
    return f"{node_cmd} {STDIO_SERVER_SCRIPT}"


# ----------------------------------------------------------------------------
# Async fixture providing a connected MCPStdioClient instance
# ----------------------------------------------------------------------------


@pytest_asyncio.fixture()
async def stdio_client(stdio_reference_command: str):  # type: ignore[override]
    client = MCPStdioClient()
    await client.connect_to_server(stdio_reference_command)
    try:
        yield client
    finally:
        with contextlib.suppress(Exception):
            await client.disconnect()


# ----------------------------------------------------------------------------
# Async fixture providing a connected MCPSseClient instance
# ----------------------------------------------------------------------------


@pytest_asyncio.fixture()
async def sse_client(sse_reference_server: str):  # type: ignore[override]
    client = MCPSseClient()
    # Use 1 second timeout for tests to fail fast since we expect SSE to fail anyway
    await client.connect_to_server(sse_reference_server, timeout_seconds=1)
    try:
        yield client
    finally:
        with contextlib.suppress(Exception):
            await client.disconnect()


# -----------------------------------------------------------------------------
# Composite fixture: parameterise over both transports to run the same test twice
# Currently only supports stdio and sse. Streamable HTTP support may be added later.
# -----------------------------------------------------------------------------


@pytest_asyncio.fixture(
    params=[
        "stdio",
        pytest.param("sse", marks=pytest.mark.xfail(reason="SSE implementation has connection validation bug")),
    ]
)
async def mcp_client(request, sse_reference_server, stdio_reference_command):  # type: ignore[override]
    """Yield a connected MCP client for the requested transport.

    * "stdio" → Launch reference stdio server command
    * "sse"   → HTTP+SSE connection to /sse endpoint
    """
    if request.param == "stdio":
        client = MCPStdioClient()
        await client.connect_to_server(stdio_reference_command)
        try:
            yield ("stdio", client)
        finally:
            await client.disconnect()
    elif request.param == "sse":
        client = MCPSseClient()
        # Use 1 second timeout for tests to fail fast since we expect SSE to fail anyway
        await client.connect_to_server(sse_reference_server, timeout_seconds=1)
        try:
            yield ("sse", client)
        finally:
            await client.disconnect()


# -----------------------------------------------------------------------------
# Derived URLs for HTTP+SSE endpoint tests
# -----------------------------------------------------------------------------


@pytest.fixture(scope="session")
def http_sse_url(sse_reference_server):
    """Return the /sse endpoint for the reference server (legacy transport)."""
    return sse_reference_server

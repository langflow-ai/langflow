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

    Yields the base MCP URL (including /mcp path) to connect to.
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

    # Provide the /mcp endpoint expected by clients
    base_url = f"http://127.0.0.1:{port}/mcp"
    yield base_url

    # Teardown - terminate process
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


# ----------------------------------------------------------------------------
# Async fixture providing a connected MCPSseClient instance
# ----------------------------------------------------------------------------

try:
    from langflow.base.mcp.sse_client import MCPSseClient
except ImportError:
    MCPSseClient = None  # type: ignore[assignment]


@pytest_asyncio.fixture()
async def sse_client(sse_reference_server):  # type: ignore[override]
    """Yield a connected *MCPSseClient* and close it afterwards."""
    if MCPSseClient is None:
        pytest.skip("MCPSseClient import failed - is langflow installed in editable mode?")

    client = MCPSseClient()
    await client.connect_to_server_with_retry(sse_reference_server)
    try:
        yield client
    finally:
        with contextlib.suppress(Exception):
            # Connection closure may race with loop shutdown
            await client.disconnect()


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

try:
    from langflow.base.mcp.stdio_client import MCPStdioClient
except ImportError:
    MCPStdioClient = None  # type: ignore[assignment]


@pytest_asyncio.fixture()
async def stdio_client(stdio_reference_command: str):  # type: ignore[override]
    if MCPStdioClient is None:
        pytest.skip("MCPStdioClient import failed - is langflow installed in editable mode?")

    client = MCPStdioClient()
    await client.connect_to_server(stdio_reference_command)
    try:
        yield client
    finally:
        with contextlib.suppress(Exception):
            await client.disconnect()


# -----------------------------------------------------------------------------
# Composite fixture: parameterise over both transports to run the same test twice
# -----------------------------------------------------------------------------

@pytest_asyncio.fixture(params=["sse", "stdio"])
async def mcp_client(request, sse_client, stdio_client):  # type: ignore[override]
    """Yield (transport_name, client) for parametrised tests.

    Tests using this fixture will automatically execute once for SSE and once
    for STDIO, ensuring parity across transports without duplicating code.
    """
    if request.param == "sse":
        return "sse", sse_client
    return "stdio", stdio_client


# -----------------------------------------------------------------------------
# Derived URLs for HTTP+SSE endpoint tests
# -----------------------------------------------------------------------------

@pytest.fixture(scope="session")
def http_sse_url(sse_reference_server):
    """Return the /sse endpoint for the reference server (legacy transport)."""
    return sse_reference_server.replace("/mcp", "/sse")

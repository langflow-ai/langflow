"""MCP tool calls must be visible to the operator's APM, on every transport.

The obvious way to get outbound spans is to instrument httpx. That does not work here: MCP's
stdio transport is a subprocess talking over stdin and stdout, so it makes no HTTP requests at
all, and it is what a locally run MCP server uses. Instrumenting httpx would have produced
spans for the other two transports only, while also producing one per outbound LLM provider
call, which the export filter cannot separate from ours because both carry the scope name
``opentelemetry.instrumentation.httpx``.

So the span is emitted at the call site under the application tracer instead. This drives a
real MCP server over real stdio to prove it, rather than asserting on a stub.

Runs in a subprocess because the tracer provider is process-global.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

pytest.importorskip("opentelemetry")
pytest.importorskip("mcp")

SENTINEL = "argument-text-that-must-not-be-exported"

# A real MCP server, small enough to inline. Started as a subprocess by the stdio client, so the
# whole path under test is genuine: process spawn, stdio framing, JSON-RPC, tool dispatch.
SERVER = '''
import asyncio
import sys
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("probe-server")


@mcp.tool()
def echo(text: str) -> str:
    """Echo the text back."""
    return f"echoed: {text}"


@mcp.tool()
def boom(text: str) -> str:
    """Fail, echoing the argument back in the error the way a real server does."""
    msg = f"tool blew up on {text}"
    raise RuntimeError(msg)


@mcp.tool()
async def slow() -> str:
    """Take long enough for the client-side timeout to fire."""
    await asyncio.sleep(10)
    return "finished"


mcp.run(transport="stdio")
'''

PROBE = f"""
import asyncio, json, sys

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

exporter = InMemorySpanExporter()
provider = TracerProvider()
provider.add_span_processor(SimpleSpanProcessor(exporter))
trace.set_tracer_provider(provider)

from lfx.base.mcp.util import MCPStdioClient
from lfx.graph.graph.base import Graph
from lfx.observability import APPLICATION_TRACER_NAME

SERVER_PATH = sys.argv[1]
SENTINEL = {SENTINEL!r}


async def main():
    client = MCPStdioClient()
    await client.connect_to_server(f"{{sys.executable}} {{SERVER_PATH}}")

    # The real helper, not a stand-in span: async_start opens it with make_current=False, and
    # that is the path where parenting was silently wrong.
    graph = Graph()
    # True is the converted shape: a coroutine caller owns the span, so it is current for the
    # whole run. False is what async_start could do on its own, and could not make current.
    make_current = sys.argv[2] == "true"
    with graph.flow_execution_span(make_current=make_current):
        flow_span_id = trace.get_current_span().get_span_context().span_id
        result = await client.run_tool("echo", arguments={{"text": SENTINEL}})
        failed = await client.run_tool("boom", arguments={{"text": SENTINEL}})
        if make_current:
            try:
                await client.run_tool("slow", arguments={{}}, timeout=0.01)
            except ValueError:
                pass

    await client.disconnect()
    provider.force_flush()

    spans = [
        {{
            "name": s.name,
            "scope": s.instrumentation_scope.name,
            "attrs": dict(s.attributes or {{}}),
            "status": s.status.status_code.name,
            # Events are a separate carrier from attributes: record_exception writes the
            # exception message into one. The leak assertion is worthless without them.
            "events": [(e.name, dict(e.attributes or {{}})) for e in s.events],
            "parent_span_id": s.parent.span_id if s.parent else None,
        }}
        for s in exporter.get_finished_spans()
    ]
    print("PROBE_RESULT " + json.dumps({{
        "spans": spans,
        "flow_span_id": flow_span_id,
        "failed_is_error": bool(getattr(failed, "isError", False)),
    }}))


asyncio.run(main())
"""


def run_probe(*, make_current: bool = True) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("OTEL_")}
    with tempfile.TemporaryDirectory() as tmp:
        server_path = Path(tmp) / "server.py"
        server_path.write_text(SERVER, encoding="utf-8")
        probe_path = Path(tmp) / "probe.py"
        probe_path.write_text(PROBE, encoding="utf-8")
        completed = subprocess.run(  # noqa: S603
            [sys.executable, str(probe_path), str(server_path), "true" if make_current else "false"],
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
    assert completed.returncode == 0, completed.stderr
    line = next(ln for ln in completed.stdout.splitlines() if ln.startswith("PROBE_RESULT "))
    return json.loads(line.removeprefix("PROBE_RESULT "))


@pytest.fixture(scope="module")
def probe_result() -> dict:
    return run_probe()


@pytest.fixture(scope="module")
def detached_probe_result() -> dict:
    """The async_start path: the flow span exists but is not attached to the OTel context."""
    return run_probe(make_current=False)


def test_an_mcp_tool_call_over_stdio_produces_a_span(probe_result):
    """The transport httpx instrumentation could never have seen."""
    tool_spans = [s for s in probe_result["spans"] if s["name"] == "mcp.tool.call"]
    echo_spans = [s for s in tool_spans if s["attrs"]["mcp.tool.name"] == "echo"]

    assert len(echo_spans) == 1, f"expected one span for the echo call, got {[s['attrs'] for s in tool_spans]}"
    assert echo_spans[0]["attrs"]["mcp.transport"] == "stdio"


def test_the_span_is_emitted_under_the_application_tracer(probe_result):
    """The scope name is what the export filter allowlists, so it is the whole mechanism."""
    from lfx.observability import APPLICATION_TRACER_NAME

    tool_span = next(s for s in probe_result["spans"] if s["name"] == "mcp.tool.call")
    assert tool_span["scope"] == APPLICATION_TRACER_NAME


def test_the_tool_span_nests_under_the_flow_span(probe_result):
    tool_span = next(s for s in probe_result["spans"] if s["name"] == "mcp.tool.call")

    assert tool_span["parent_span_id"] == probe_result["flow_span_id"]


def test_tool_arguments_never_reach_the_span(probe_result):
    """Tool arguments carry flow data, so only identifiers may be recorded.

    The serialized span carries events as well as attributes. A failing tool echoes the argument
    back inside its error text, so without events in the blob this asserts against a shape that
    structurally cannot hold the leak it is guarding.
    """
    blob = json.dumps(probe_result["spans"])

    assert SENTINEL not in blob, f"tool argument reached the APM: {blob}"


def test_a_failed_tool_call_is_not_exported_as_a_success(probe_result):
    """MCP reports failure in the result, not by raising, so nothing raises through the span."""
    assert probe_result["failed_is_error"], "the boom tool was supposed to fail"

    spans = [s for s in probe_result["spans"] if s["name"] == "mcp.tool.call"]
    failed = [s for s in spans if s["attrs"]["mcp.tool.name"] == "boom" and s["status"] == "ERROR"]
    assert len(failed) == 1, f"expected one failed tool span, got {[(s['attrs'], s['status']) for s in spans]}"
    assert failed[0]["attrs"]["mcp.tool.name"] == "boom"
    assert failed[0]["attrs"]["error.type"] == "ToolError"


def test_a_timed_out_tool_call_reports_the_timeout_type(probe_result):
    timed_out = next(
        s for s in probe_result["spans"] if s["name"] == "mcp.tool.call" and s["attrs"]["mcp.tool.name"] == "slow"
    )

    assert timed_out["status"] == "ERROR"
    assert timed_out["attrs"]["error.type"] == "TimeoutError"


def test_the_server_is_identified_on_the_span(probe_result):
    """Two servers can expose the same tool name, so the tool name alone attributes nothing."""
    tool_span = next(s for s in probe_result["spans"] if s["name"] == "mcp.tool.call")

    assert tool_span["attrs"]["mcp.server"]


@pytest.mark.parametrize(
    ("url", "expected_server"),
    [
        (
            "http://alice:secret-token@127.0.0.1:9931/mcp?api_key=query-secret",  # pragma: allowlist secret
            "127.0.0.1:9931",
        ),
        ("https://alice:secret-token@[2001:db8::1]:0/mcp", "[2001:db8::1]:0"),  # pragma: allowlist secret
    ],
)
def test_http_server_attribute_strips_url_userinfo(url, expected_server):
    from lfx.base.mcp.util import MCPStreamableHttpClient

    client = MCPStreamableHttpClient(tool_execution_timeout=1)
    client._connection_params = {"url": url}

    attributes = client._tool_span_attributes("echo")

    assert attributes["mcp.server"] == expected_server
    assert "alice" not in attributes["mcp.server"]
    assert "secret-token" not in attributes["mcp.server"]


def test_a_detached_flow_span_cannot_parent_the_tool_span(detached_probe_result):
    """Why the span had to move to the caller, pinned so the reason does not get lost.

    A span that is not current cannot be a parent: the tool span starts its own trace instead.
    That is what async_start could do on its own, being a generator, and it is why the callers
    now open the span and pass open_flow_span=False.
    """
    tool_span = next(s for s in detached_probe_result["spans"] if s["name"] == "mcp.tool.call")

    assert tool_span["parent_span_id"] is None

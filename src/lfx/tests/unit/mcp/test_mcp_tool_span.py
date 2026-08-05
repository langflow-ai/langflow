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
import sys
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("probe-server")


@mcp.tool()
def echo(text: str) -> str:
    """Echo the text back."""
    return f"echoed: {text}"


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
from lfx.observability import APPLICATION_TRACER_NAME

SERVER_PATH = sys.argv[1]
SENTINEL = {SENTINEL!r}


async def main():
    client = MCPStdioClient()
    await client.connect_to_server(f"{{sys.executable}} {{SERVER_PATH}}")

    tracer = trace.get_tracer(APPLICATION_TRACER_NAME)
    # A flow span stands in for a real run, so the parenting assertion is meaningful.
    with tracer.start_as_current_span("flow.execute") as flow_span:
        flow_span_id = flow_span.get_span_context().span_id
        result = await client.run_tool("echo", arguments={{"text": SENTINEL}})

    await client.disconnect()
    provider.force_flush()

    spans = [
        {{
            "name": s.name,
            "scope": s.instrumentation_scope.name,
            "attrs": dict(s.attributes or {{}}),
            "parent_span_id": s.parent.span_id if s.parent else None,
        }}
        for s in exporter.get_finished_spans()
    ]
    print("PROBE_RESULT " + json.dumps({{"spans": spans, "flow_span_id": flow_span_id}}))


asyncio.run(main())
"""


def run_probe() -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("OTEL_")}
    with tempfile.TemporaryDirectory() as tmp:
        server_path = Path(tmp) / "server.py"
        server_path.write_text(SERVER, encoding="utf-8")
        probe_path = Path(tmp) / "probe.py"
        probe_path.write_text(PROBE, encoding="utf-8")
        completed = subprocess.run(  # noqa: S603
            [sys.executable, str(probe_path), str(server_path)],
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


def test_an_mcp_tool_call_over_stdio_produces_a_span(probe_result):
    """The transport httpx instrumentation could never have seen."""
    tool_spans = [s for s in probe_result["spans"] if s["name"] == "mcp.tool.call"]

    assert len(tool_spans) == 1, f"expected one tool span, got {[s['name'] for s in probe_result['spans']]}"
    span = tool_spans[0]
    assert span["attrs"]["mcp.tool.name"] == "echo"
    assert span["attrs"]["mcp.transport"] == "stdio"


def test_the_span_is_emitted_under_the_application_tracer(probe_result):
    """The scope name is what the export filter allowlists, so it is the whole mechanism."""
    from lfx.observability import APPLICATION_TRACER_NAME

    tool_span = next(s for s in probe_result["spans"] if s["name"] == "mcp.tool.call")
    assert tool_span["scope"] == APPLICATION_TRACER_NAME


def test_the_tool_span_nests_under_the_flow_span(probe_result):
    tool_span = next(s for s in probe_result["spans"] if s["name"] == "mcp.tool.call")

    assert tool_span["parent_span_id"] == probe_result["flow_span_id"]


def test_tool_arguments_never_reach_the_span(probe_result):
    """Tool arguments carry flow data, so only identifiers may be recorded."""
    blob = json.dumps(probe_result["spans"])

    assert SENTINEL not in blob, f"tool argument reached the APM: {blob}"

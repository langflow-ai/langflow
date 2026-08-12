"""An outbound A2A call must be visible to the operator's APM, carrying identifiers only.

The MCP half of this shipped first; A2A is the other outbound call the runtime makes itself.
Instrumenting httpx would not do it: httpx is the transport the LLM vendor SDKs ride on, and
the export filter allowlists by instrumentation scope name, so their spans and ours would be
the same string. The span is emitted at the call site under the application tracer instead.

This drives a real A2A server (the a2a-sdk server stack, over real HTTP on loopback) with the
real a2a-sdk client, so the whole path under test is genuine: card fetch, JSON-RPC
message/send, task events. The test lives here rather than in ``src/lfx/tests`` because the
a2a SDK is a langflow-base dependency, not an lfx one, so the lfx test env cannot import it.

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
pytest.importorskip("a2a")

SENTINEL = "message-text-that-must-not-be-exported"
AGENT_NAME = "probe-agent"

PROBE = f'''
import asyncio, json, socket, sys

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

exporter = InMemorySpanExporter()
provider = TracerProvider()
provider.add_span_processor(SimpleSpanProcessor(exporter))
trace.set_tracer_provider(provider)

import uvicorn
from a2a.helpers.proto_helpers import new_text_part
from a2a.server.agent_execution import AgentExecutor
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.types import a2a_pb2 as pb
from a2a.utils.constants import PROTOCOL_VERSION_CURRENT, TransportProtocol
from starlette.applications import Starlette

from lfx.components.models_and_agents.a2a_agent import build_a2a_client, call_a2a_agent
from lfx.graph.graph.base import Graph

SENTINEL = {SENTINEL!r}


class ProbeExecutor(AgentExecutor):
    """A real agent: completes with an artifact, or fails the task echoing the message back.

    The failing arm is what a real remote does with a bad request, and it puts the caller's
    message inside the failure text the client raises on.
    """

    async def execute(self, context, event_queue) -> None:
        text = context.get_user_input()
        await event_queue.enqueue_event(
            pb.Task(
                id=context.task_id,
                context_id=context.context_id,
                status=pb.TaskStatus(state=pb.TaskState.TASK_STATE_SUBMITTED),
            )
        )
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        await updater.start_work()
        if "boom" in text:
            await updater.failed(updater.new_agent_message([new_text_part(f"agent blew up on {{text}}")]))
            return
        await updater.add_artifact([new_text_part(f"echoed: {{text}}")], name="result")
        await updater.complete()

    async def cancel(self, context, event_queue) -> None:
        await TaskUpdater(event_queue, context.task_id, context.context_id).cancel()


def build_app(port):
    card = pb.AgentCard(
        name={AGENT_NAME!r},
        description="probe",
        version="1.0",
        supported_interfaces=[
            pb.AgentInterface(
                url=f"http://127.0.0.1:{{port}}/",
                protocol_binding=TransportProtocol.JSONRPC.value,
                protocol_version=PROTOCOL_VERSION_CURRENT,
            )
        ],
        capabilities=pb.AgentCapabilities(streaming=False),
        default_input_modes=["application/json"],
        default_output_modes=["application/json"],
        skills=[pb.AgentSkill(id="echo", name="echo", description="echo", tags=["echo"])],
    )
    handler = DefaultRequestHandler(agent_executor=ProbeExecutor(), task_store=InMemoryTaskStore(), agent_card=card)
    return Starlette(routes=[*create_agent_card_routes(card), *create_jsonrpc_routes(handler, rpc_url="/")])


async def main():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(build_app(port), log_level="warning"))
    serving = asyncio.create_task(server.serve(sockets=[sock]))
    while not server.started:
        await asyncio.sleep(0.05)

    agent_url = f"http://127.0.0.1:{{port}}"
    failed_raised = False
    # The production client (api key pinned to the origin, SSRF-protected transport), not a
    # bare httpx.AsyncClient.
    async with build_a2a_client(agent_url, ["127.0.0.1"], timeout=30) as client:
        graph = Graph()
        with graph.flow_execution_span():
            flow_span_id = trace.get_current_span().get_span_context().span_id
            answer = await call_a2a_agent(agent_url, SENTINEL, httpx_client=client)
            try:
                await call_a2a_agent(agent_url, f"boom {{SENTINEL}}", httpx_client=client)
            except ValueError:
                failed_raised = True

    server.should_exit = True
    await serving
    provider.force_flush()

    spans = [
        {{
            "name": s.name,
            "scope": s.instrumentation_scope.name,
            "attrs": dict(s.attributes or {{}}),
            "status": s.status.status_code.name,
            # Events are a separate carrier from attributes: record_exception writes the
            # exception message into one, and the a2a failure text embeds the caller's message.
            "events": [(e.name, dict(e.attributes or {{}})) for e in s.events],
            "parent_span_id": s.parent.span_id if s.parent else None,
        }}
        for s in exporter.get_finished_spans()
    ]
    print("PROBE_RESULT " + json.dumps({{
        "spans": spans,
        "flow_span_id": flow_span_id,
        "answer": answer,
        "failed_raised": failed_raised,
        "port": port,
    }}))


asyncio.run(main())
'''


@pytest.fixture(scope="module")
def probe_result() -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("OTEL_")}
    with tempfile.TemporaryDirectory() as tmp:
        probe_path = Path(tmp) / "probe.py"
        probe_path.write_text(PROBE, encoding="utf-8")
        completed = subprocess.run(  # noqa: S603
            [sys.executable, str(probe_path)],
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
    assert completed.returncode == 0, completed.stderr
    line = next(ln for ln in completed.stdout.splitlines() if ln.startswith("PROBE_RESULT "))
    return json.loads(line.removeprefix("PROBE_RESULT "))


def _call_spans(probe_result: dict) -> list[dict]:
    return [s for s in probe_result["spans"] if s["name"] == "a2a.message.send"]


def test_the_probe_really_talked_to_the_remote_agent(probe_result):
    """Guards every other assertion here: no round-trip, no evidence about the span."""
    assert probe_result["answer"] == f"echoed: {SENTINEL}"
    assert probe_result["failed_raised"], "the boom call was supposed to raise"


def test_an_a2a_call_produces_one_span(probe_result):
    """One span per call, covering the card resolve and the message/send together."""
    assert len(_call_spans(probe_result)) == 2, [s["attrs"] for s in probe_result["spans"]]


def test_the_span_is_emitted_under_the_application_tracer(probe_result):
    """The scope name is what the export filter allowlists, so it is the whole mechanism."""
    from lfx.observability import APPLICATION_TRACER_NAME

    assert {s["scope"] for s in _call_spans(probe_result)} == {APPLICATION_TRACER_NAME}


def test_the_a2a_span_nests_under_the_flow_span(probe_result):
    for span in _call_spans(probe_result):
        assert span["parent_span_id"] == probe_result["flow_span_id"]


def test_the_agent_is_identified_without_its_url(probe_result):
    """Host and card name, never the URL: a URL carries credentials in its query string."""
    span = _call_spans(probe_result)[0]

    assert span["attrs"]["a2a.agent.host"] == f"127.0.0.1:{probe_result['port']}"
    assert span["attrs"]["a2a.agent.name"] == AGENT_NAME
    assert "http" not in json.dumps(span["attrs"]), span["attrs"]


def test_the_message_never_reaches_the_span(probe_result):
    """The message is flow data. The failing agent echoes it into the error the client raises on."""
    from lfx.observability import APPLICATION_TRACER_NAME

    blob = json.dumps([s for s in probe_result["spans"] if s["scope"] == APPLICATION_TRACER_NAME])

    assert SENTINEL not in blob, f"the message reached the APM: {blob}"


def test_a_failed_remote_task_is_exported_as_an_error(probe_result):
    """A2A raises on a non-completed task, so the span's except arm is what records this."""
    failed = [s for s in _call_spans(probe_result) if s["status"] == "ERROR"]

    assert len(failed) == 1, [(s["attrs"], s["status"]) for s in _call_spans(probe_result)]
    assert failed[0]["attrs"]["error.type"] == "ValueError"
    assert not failed[0]["events"], failed[0]["events"]


def test_the_sdk_own_spans_are_not_exported(probe_result):
    """The a2a SDK instruments itself against whatever global provider exists, i.e. ours.

    Its spans record exceptions the SDK way, message and stack trace included, and they ride the
    same provider as ours. Only the allowlist keeps them out of the operator's APM.
    """
    from lfx.observability import APPLICATION_INSTRUMENTATION_SCOPES, APPLICATION_TRACER_NAME

    sdk_scopes = {s["scope"] for s in probe_result["spans"]} - {APPLICATION_TRACER_NAME}

    assert sdk_scopes, "the SDK emitted no spans, so this test proves nothing"
    assert not sdk_scopes & APPLICATION_INSTRUMENTATION_SCOPES, sdk_scopes

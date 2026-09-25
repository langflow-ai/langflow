"""OTel queue semantics for the bounded background executor."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

pytest.importorskip("opentelemetry.sdk.trace.export.in_memory_span_exporter")

PROBE = r"""
import asyncio
import json

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind

exporter = InMemorySpanExporter()
provider = TracerProvider()
provider.add_span_processor(SimpleSpanProcessor(exporter))
trace.set_tracer_provider(provider)

from langflow.services.background_execution.executor import InProcessExecutor
from lfx.observability import application_span


async def main():
    executor = InProcessExecutor(max_concurrency=1)
    await executor.start()
    done = asyncio.Event()

    async def work():
        with application_span("work.child"):
            done.set()

    attributes = {
        "messaging.system": "langflow",
        "messaging.destination.name": "workflow.jobs",
        "messaging.operation.type": "send",
        "langflow.job.id": "job-1",
    }
    with application_span("langflow.job.enqueue", attributes, kind=SpanKind.PRODUCER):
        await executor.submit("job-1", work)
    await asyncio.wait_for(done.wait(), timeout=2)
    await executor._queue.join()
    await executor.stop()
    provider.force_flush()

    spans = [
        {
            "name": span.name,
            "span_id": span.context.span_id,
            "parent": span.parent.span_id if span.parent else None,
            "links": [link.context.span_id for link in span.links],
            "kind": span.kind.name,
            "attributes": dict(span.attributes or {}),
            "duration": span.end_time - span.start_time,
        }
        for span in exporter.get_finished_spans()
    ]
    print("PROBE_RESULT " + json.dumps(spans))


asyncio.run(main())
"""


def test_queue_spans_use_producer_consumer_links_and_parent_execution_work():
    env = {key: value for key, value in os.environ.items() if not key.startswith("OTEL_")}
    with tempfile.TemporaryDirectory() as tmp:
        probe_path = Path(tmp) / "probe.py"
        probe_path.write_text(PROBE, encoding="utf-8")
        completed = subprocess.run(  # noqa: S603
            [sys.executable, str(probe_path)],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    assert completed.returncode == 0, completed.stderr
    line = next(line for line in completed.stdout.splitlines() if line.startswith("PROBE_RESULT "))
    spans = json.loads(line.removeprefix("PROBE_RESULT "))
    by_name = {span["name"]: span for span in spans}

    producer = by_name["langflow.job.enqueue"]
    queue_wait = by_name["langflow.job.queue_wait"]
    dequeue = by_name["langflow.job.dequeue"]
    execute = by_name["langflow.job.execute"]
    child = by_name["work.child"]

    assert producer["kind"] == "PRODUCER"
    assert dequeue["kind"] == "CONSUMER"
    assert execute["kind"] == "CONSUMER"
    assert producer["span_id"] in queue_wait["links"]
    assert producer["span_id"] in dequeue["links"]
    assert producer["span_id"] in execute["links"]
    assert execute["parent"] is None
    assert child["parent"] == execute["span_id"]
    assert queue_wait["duration"] > 0
    assert queue_wait["attributes"]["langflow.phase"] == "job.queue_wait"
    assert dequeue["attributes"]["langflow.phase"] == "job.dequeue"
    assert execute["attributes"]["langflow.phase"] == "job.execute"
    assert execute["attributes"]["messaging.operation.type"] == "process"

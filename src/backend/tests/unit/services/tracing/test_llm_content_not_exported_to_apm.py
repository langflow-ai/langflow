"""End-to-end check that a real LLM tracer cannot push prompt text to the operator's APM.

Traceloop adopts an already-installed global tracer provider and appends its own span
processor to it, so once Langflow installs one for OTLP export, its gen_ai spans travel
that path too. The vendor integration is deliberately left alone; the export filter is
what holds the line. Runs in a subprocess because tracer providers are process-global.
"""

import json
import os
import subprocess
import sys

SENTINEL = "SENTINEL-PROMPT-TEXT-MUST-NOT-BE-EXPORTED"

PROBE = f"""
import json
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from langflow.services.telemetry.opentelemetry import (
    APPLICATION_TRACER_NAME,
    ApplicationOnlySpanProcessor,
)

# Stand in for the operator's APM, wired exactly as the OTLP bootstrap wires it.
apm_exporter = InMemorySpanExporter()
provider = TracerProvider()
provider.add_span_processor(ApplicationOnlySpanProcessor(apm_exporter))
trace.set_tracer_provider(provider)

from uuid import uuid4
from langflow.services.tracing.traceloop import TraceloopTracer

tracer = TraceloopTracer(
    trace_name="probe", trace_type="chain", project_name="probe-project", trace_id=uuid4()
)

# Drive the vendor integration the way a flow does, with content in the payload.
if tracer.ready:
    tracer.add_trace(
        trace_id=str(uuid4()),
        trace_name="OpenAIModel",
        trace_type="llm",
        inputs={{"input_value": {SENTINEL!r}}},
    )
    tracer.end_trace(trace_id=list(tracer.child_spans)[0], trace_name="OpenAIModel") if tracer.child_spans else None

# An application span must still get through, so we know the filter is not simply off.
provider.get_tracer(APPLICATION_TRACER_NAME).start_span("flow").end()
provider.force_flush()

finished = apm_exporter.get_finished_spans()
blob = json.dumps(
    [{{"name": s.name, "scope": s.instrumentation_scope.name, "attrs": dict(s.attributes or {{}})}} for s in finished],
    default=str,
)
print("PROBE_RESULT " + json.dumps({{
    "ready": bool(tracer.ready),
    "exported": [s.name for s in finished],
    "leaked": {SENTINEL!r} in blob,
}}))
"""


def test_traceloop_content_never_reaches_the_apm_exporter():
    env = {k: v for k, v in os.environ.items() if not k.startswith(("OTEL_", "TRACELOOP_"))}
    env["TRACELOOP_API_KEY"] = "not-a-real-key"  # pragma: allowlist secret
    # Traceloop's own exporter points at a closed port so nothing leaves the machine.
    env["TRACELOOP_BASE_URL"] = "http://127.0.0.1:9"
    completed = subprocess.run(  # noqa: S603
        [sys.executable, "-c", PROBE],
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    line = next(ln for ln in completed.stdout.splitlines() if ln.startswith("PROBE_RESULT "))
    result = json.loads(line.removeprefix("PROBE_RESULT "))

    assert result["ready"], "Traceloop tracer did not initialize; the probe proves nothing"
    assert not result["leaked"], "LLM content reached the APM exporter"
    assert result["exported"] == ["flow"], f"expected only the application span, got {result['exported']}"

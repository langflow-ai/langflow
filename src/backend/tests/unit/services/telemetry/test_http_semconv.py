"""The semantic convention opt-in is process-global and read once, so each case is a subprocess."""

import json
import os
import subprocess
import sys

# Stable names, emitted since OTel HTTP semconv 1.0. APMs key their HTTP dashboards and
# service maps off these; the pre-1.0 names leave the per-endpoint breakdown empty.
STABLE = {"http.route", "http.request.method", "http.response.status_code"}
LEGACY = {"http.target", "http.method", "http.status_code"}

PROBE = """
import json
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

exporter = InMemorySpanExporter()
provider = TracerProvider()
provider.add_span_processor(SimpleSpanProcessor(exporter))
trace.set_tracer_provider(provider)

from fastapi import FastAPI
from fastapi.testclient import TestClient
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

app = FastAPI()

@app.get("/flows/{flow_id}")
def read_flow(flow_id: str):
    return {"id": flow_id}

# Mirror langflow.main.create_app: the opt-in must be set before instrumentation.
import os
os.environ.setdefault("OTEL_SEMCONV_STABILITY_OPT_IN", "http")
FastAPIInstrumentor.instrument_app(app)

# A real request through a real route, so the attributes are whatever the server actually set.
TestClient(app).get("/flows/11111111-1111-1111-1111-111111111111")
provider.force_flush()

server = [s for s in exporter.get_finished_spans() if s.kind.name == "SERVER"]
print("PROBE_RESULT " + json.dumps({"attrs": dict(server[0].attributes)}))
"""


def run_probe(env_overrides: dict[str, str]) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("OTEL_")}
    env.update(env_overrides)
    completed = subprocess.run(  # noqa: S603
        [sys.executable, "-c", PROBE],
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    line = next(ln for ln in completed.stdout.splitlines() if ln.startswith("PROBE_RESULT "))
    return json.loads(line.removeprefix("PROBE_RESULT "))


def test_http_spans_use_the_stable_semantic_conventions():
    """Without the opt-in the FastAPI instrumentation still emits the pre-1.0 attribute names."""
    attrs = run_probe({})["attrs"]

    assert set(attrs) >= STABLE, f"missing stable attributes: {STABLE - set(attrs)}"
    assert not (LEGACY & set(attrs)), f"still emitting legacy attributes: {LEGACY & set(attrs)}"

    # The templated route, not the request path: the raw path carries flow ids, and this
    # attribute reaches metric labels, where per-flow cardinality is unbounded.
    assert attrs["http.route"] == "/flows/{flow_id}"
    assert attrs["http.request.method"] == "GET"
    assert attrs["http.response.status_code"] == 200


def test_an_operator_can_still_opt_into_emitting_both():
    """setdefault, not an assignment, so a migration can ask for the old names alongside."""
    attrs = run_probe({"OTEL_SEMCONV_STABILITY_OPT_IN": "http/dup"})["attrs"]

    assert set(attrs) >= STABLE
    assert set(attrs) >= LEGACY

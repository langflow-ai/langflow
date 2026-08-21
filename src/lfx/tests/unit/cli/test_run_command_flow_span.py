"""``lfx run``'s one-shot CLI must label its flow span like every server surface does.

This is the runtime with no server in front of it, which makes it the cell most likely to be
forgotten: there is no request to hang telemetry off, so the flow span is the only record that
the run happened at all. ``cli/run.py`` binds ``lfx.run`` around the whole await, and this
drives the real command rather than that context manager, so a refactor that moves the binding
off the command's path is caught.

Runs in a subprocess because the tracer provider is process-global and installed once.

This installs its own in-memory provider, so it proves the attribute is bound on the right
span and nothing about delivery. Whether the command installs a provider from the OTEL_* env
vars and flushes it before the process exits is ``test_run_command_otlp_export.py``'s job.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

# opentelemetry is an optional lfx extra (``lfx[otel]``); skip rather than error on an install
# that did not opt in, matching the sibling serve probe.
pytest.importorskip("opentelemetry")

FLOW = Path(__file__).resolve().parents[2] / "data" / "simple_chat_no_llm.json"

PROBE = """
import json, sys

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

exporter = InMemorySpanExporter()
provider = TracerProvider()
provider.add_span_processor(SimpleSpanProcessor(exporter))
trace.set_tracer_provider(provider)

# A meter provider too: the table says this cell has no server, so "no HTTP server metric" is
# part of what passes here, and an assertion about absence needs a reader that would have seen
# one had it been recorded.
from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader

reader = InMemoryMetricReader()
metrics.set_meter_provider(MeterProvider(metric_readers=[reader]))

from typer.testing import CliRunner

from lfx.__main__ import app

result = CliRunner().invoke(app, ["run", sys.argv[1], "--input-value", "hello operator"])

provider.force_flush()
spans = [
    {"name": s.name, "attrs": dict(s.attributes)}
    for s in exporter.get_finished_spans()
    if s.name == "flow.execute"
]

metric_names = []
data = reader.get_metrics_data()
for resource_metric in (data.resource_metrics if data else []):
    for scope_metric in resource_metric.scope_metrics:
        for metric in scope_metric.metrics:
            metric_names.append(metric.name)

print(
    "PROBE_RESULT "
    + json.dumps(
        {
            "exit_code": result.exit_code,
            "spans": spans,
            "metrics": sorted(set(metric_names)),
        }
    )
)
"""


def run_probe() -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("OTEL_")}
    with tempfile.TemporaryDirectory() as tmp:
        # A file rather than -c: Component.__init__ reads its own class source with inspect.
        probe_path = Path(tmp) / "probe.py"
        probe_path.write_text(PROBE, encoding="utf-8")
        completed = subprocess.run(  # noqa: S603
            [sys.executable, str(probe_path), str(FLOW)],
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
    assert completed.returncode == 0, completed.stderr
    line = next(ln for ln in completed.stdout.splitlines() if ln.startswith("PROBE_RESULT "))
    return json.loads(line.removeprefix("PROBE_RESULT "))


def test_the_run_command_labels_its_flow_span():
    result = run_probe()
    assert result["exit_code"] == 0, result

    assert len(result["spans"]) == 1, f"expected one flow span, got {result['spans']}"
    attrs = result["spans"][0]["attrs"]
    assert attrs["protocol"] == "lfx.run"
    assert attrs["status"] == "ok"


def test_the_run_command_records_no_http_server_metric():
    """The N/A half of this cell: a CLI run has no server, so it must not report one.

    An HTTP server metric appearing here would mean the one-shot path had started or
    instrumented a server, which is the silent-no-op class the table exists to rule out.
    """
    result = run_probe()

    http_metrics = [name for name in result["metrics"] if name.startswith("http.server")]
    assert http_metrics == [], result["metrics"]

"""The HTTP server metrics must carry the stable semantic-convention names.

An APM keys its HTTP dashboards and service maps off the stable names, so emitting the
pre-stable ones leaves the curated views empty while ingest looks perfectly healthy. It is
also a rename once corrected, so every dashboard built on the old names has to be rebuilt.

Importing ``lfx.observability`` sets ``OTEL_SEMCONV_STABILITY_OPT_IN``. This must happen before
OpenTelemetry's instrumentation package first initialises, because it reads the value once and
caches it for the life of the process.

Runs in a subprocess because the decision is cached process-wide and cannot be re-made.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

pytest.importorskip("opentelemetry.instrumentation.fastapi")

PROBE = """
import asyncio, json

from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader

reader = InMemoryMetricReader()
metrics.set_meter_provider(MeterProvider(metric_readers=[reader]))

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from lfx.observability import bootstrap_application_telemetry, instrument_fastapi_app

# The load-bearing line. This is what both runtimes call before instrumenting their app, and
# its SystemMetricsInstrumentor pulls in OpenTelemetry's instrumentation package, freezing the
# semconv decision. Without this call the probe passes whether or not the fix is present.
bootstrap_application_telemetry()

app = FastAPI()


@app.post("/ping")
async def ping(payload: dict):
    return {"ok": True, "got": payload}


instrument_fastapi_app(app)


async def main():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://probe") as client:
        response = await client.post("/ping", json={"hello": "operator"})
        assert response.status_code == 200, response.status_code


asyncio.run(main())

names = []
data = reader.get_metrics_data()
for resource_metric in (data.resource_metrics if data else []):
    for scope_metric in resource_metric.scope_metrics:
        for metric in scope_metric.metrics:
            names.append(metric.name)

print("PROBE_RESULT " + json.dumps(sorted(set(names))))
"""


def run_probe() -> list[str]:
    # Strip inherited OTEL_ vars: OTEL_SEMCONV_STABILITY_OPT_IN set outside would decide the
    # thing under test, and the probe would pass without the code being right.
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


def test_the_server_duration_metric_uses_the_stable_name():
    """``http.server.request.duration``, not the pre-stable ``http.server.duration``."""
    names = run_probe()

    assert "http.server.request.duration" in names, names
    assert "http.server.duration" not in names, names


def test_the_payload_size_metrics_use_the_stable_names():
    """The same opt-in renames these, so they catch a partial application of the fix.

    The probe POSTs a body rather than GETting: the request-size histogram is only recorded
    when there is a body to measure, so a GET would leave this passing on an absence.
    """
    names = run_probe()

    assert "http.server.request.body.size" in names, names
    assert "http.server.response.body.size" in names, names
    assert "http.server.request.size" not in names, names
    assert "http.server.response.size" not in names, names

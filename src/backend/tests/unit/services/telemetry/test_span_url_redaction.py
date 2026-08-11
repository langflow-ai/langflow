"""The operator's APM must never receive a credential that travelled in a URL.

``lfx serve`` accepts its API key as a query parameter (``APIKeyQuery``), and the FastAPI
server span records ``url.query`` verbatim. That scope is on the export allowlist, so before
this the key went to whatever OTLP backend the operator configured.

Runs in a subprocess because the tracer provider is process-global.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from lfx.observability import APPLICATION_INSTRUMENTATION_SCOPES

SECRET = "lfx-serve-api-key-NOT-REAL"  # noqa: S105  # pragma: allowlist secret

# The server span is already allowlisted, and ``lfx serve`` accepts its API key as a query
# parameter, so this is a live path today rather than a hypothetical one.
SERVER_SPAN_PROBE = f"""
import asyncio, json

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from lfx.observability import ApplicationOnlySpanProcessor, instrument_fastapi_app

exporter = InMemorySpanExporter()
provider = TracerProvider()
provider.add_span_processor(ApplicationOnlySpanProcessor(exporter))
trace.set_tracer_provider(provider)

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

app = FastAPI()


@app.get("/flows/run")
async def run():
    return {{"ok": True}}


instrument_fastapi_app(app)
SECRET = {SECRET!r}


async def main():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://probe") as client:
        await client.get(f"/flows/run?x-api-key={{SECRET}}&flow=abc")
    provider.force_flush()
    spans = [
        {{"name": s.name, "attrs": dict(s.attributes)}}
        for s in exporter.get_finished_spans()
        if s.attributes and "url.path" in s.attributes
    ]
    print("PROBE_RESULT " + json.dumps({{"spans": spans}}))


asyncio.run(main())
"""


def run_probe(source: str) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("OTEL_")}
    with tempfile.TemporaryDirectory() as tmp:
        probe_path = Path(tmp) / "probe.py"
        probe_path.write_text(source, encoding="utf-8")
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


def test_the_serve_api_key_never_reaches_the_apm():
    """Regression for a live leak: the key is accepted as a query param and the span kept it."""
    result = run_probe(SERVER_SPAN_PROBE)

    assert result["spans"], "expected a server span carrying url.path"
    blob = json.dumps(result["spans"])
    assert SECRET not in blob, f"serve API key reached the APM: {blob}"


def test_redaction_keeps_the_route_an_operator_needs():
    """Blanking everything would be safe and useless; path and method must survive."""
    result = run_probe(SERVER_SPAN_PROBE)
    attrs = result["spans"][0]["attrs"]

    assert attrs["url.path"] == "/flows/run"
    assert attrs["url.query"] == ""
    assert attrs["http.request.method"] == "GET"


def test_outbound_http_scopes_stay_out_of_the_allowlist():
    """Redacting URLs does not make the LLM transports safe to export; that boundary stands."""
    for scope in (
        "opentelemetry.instrumentation.httpx",
        "opentelemetry.instrumentation.requests",
        "opentelemetry.instrumentation.urllib3",
    ):
        assert scope not in APPLICATION_INSTRUMENTATION_SCOPES

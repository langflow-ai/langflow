"""A streamed response must export one server span, not one span per frame.

The ASGI middleware can open a child span for every message it relays ("<route> http send" and
"http receive"). On a server-sent-events route that is one span per frame, all created, exported
and then usually dropped at the collector. ``instrument_fastapi_app`` turns them off; the server
span must still carry the route and status code.

Runs in a subprocess because the tracer provider is process-global.
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

FRAMES = 12

PROBE = f"""
import asyncio, json

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from lfx.observability import instrument_fastapi_app

exporter = InMemorySpanExporter()
provider = TracerProvider()
provider.add_span_processor(SimpleSpanProcessor(exporter))
trace.set_tracer_provider(provider)

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from httpx import ASGITransport, AsyncClient

app = FastAPI()


@app.post("/stream")
async def stream(payload: dict):
    async def frames():
        for i in range({FRAMES}):
            yield f"data: {{i}}\\n\\n"

    return StreamingResponse(frames(), media_type="text/event-stream")


instrument_fastapi_app(app)


async def main():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://probe") as client:
        response = await client.post("/stream", json={{"hello": "operator"}})
        assert response.status_code == 200, response.status_code
        assert response.text.count("data:") == {FRAMES}, response.text


asyncio.run(main())
provider.force_flush()
spans = [
    {{"name": s.name, "kind": s.kind.name, "attrs": dict(s.attributes or {{}})}}
    for s in exporter.get_finished_spans()
]
print("PROBE_RESULT " + json.dumps(spans))
"""


def run_probe() -> list[dict]:
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
    lines = [ln for ln in completed.stdout.splitlines() if ln.startswith("PROBE_RESULT ")]
    assert lines, f"probe printed no result.\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
    return json.loads(lines[0].removeprefix("PROBE_RESULT "))


def test_streamed_response_exports_the_server_span_without_per_message_spans():
    spans = run_probe()

    per_message = [s["name"] for s in spans if s["name"].endswith((" http send", " http receive"))]
    assert per_message == [], f"expected no per-message ASGI spans, got {len(per_message)}: {per_message[:3]}"

    server = [s for s in spans if s["kind"] == "SERVER"]
    assert len(server) == 1, spans
    assert server[0]["name"] == "POST /stream"
    assert server[0]["attrs"]["http.route"] == "/stream"
    assert server[0]["attrs"]["http.response.status_code"] == 200

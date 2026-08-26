"""An operator must be able to ship traces and metrics while keeping logs out of the APM.

Logs are the signal with the residual exposure and the GB-billed cost, so "everything except
logs" is the configuration a cost- or privacy-conscious deployment actually wants. The startup
line tells operators to set ``OTEL_LOGS_EXPORTER=none`` for exactly this, and until now nothing
checked that the advice worked.

The negative alone would pass on a broken pipeline that sent nothing at all, so the same run
asserts spans still arrive. That pairing is the point: logs off, traces on.

Runs in a subprocess against a real loopback receiver rather than an in-memory exporter,
because what is being tested is what leaves the process.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

pytest.importorskip("opentelemetry.sdk.trace")

PROBE = """
import time

from lfx.log.logger import configure, logger

# Order matters and mirrors both runtimes: the structlog chain installed here is what carries
# records to the OTLP emitter, so configuring after bootstrap would export nothing.
configure(log_level="INFO")

from lfx.observability import APPLICATION_TRACER_NAME, bootstrap_application_telemetry

telemetry = bootstrap_application_telemetry()

from opentelemetry import trace

# The allowlisted scope. A span from any other tracer is dropped on export by design, so using
# the wrong name here would make the trace assertion fail for an unrelated reason.
tracer = trace.get_tracer(APPLICATION_TRACER_NAME)
with tracer.start_as_current_span("flow.execute") as span:
    span.set_attribute("protocol", "probe")

logger.warning("a log line whose export is the thing under test")

if telemetry is not None and getattr(telemetry, "shutdown", None):
    telemetry.shutdown()

time.sleep(1)
print("PROBE_DONE")
"""


class _Recorder(BaseHTTPRequestHandler):
    paths: list[str] = []

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        self.rfile.read(length)
        type(self).paths.append(self.path)
        self.send_response(200)
        self.send_header("Content-Type", "application/x-protobuf")
        self.end_headers()
        self.wfile.write(b"")

    def log_message(self, *args):
        pass


def _run_probe(port: int, *, logs_exporter: str | None) -> list[str]:
    _Recorder.paths = []
    server = HTTPServer(("127.0.0.1", port), _Recorder)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        env = {k: v for k, v in os.environ.items() if not k.startswith("OTEL_")}
        env["OTEL_EXPORTER_OTLP_ENDPOINT"] = f"http://127.0.0.1:{port}"
        env["OTEL_EXPORTER_OTLP_PROTOCOL"] = "http/protobuf"
        env["OTEL_SERVICE_NAME"] = "langflow"
        if logs_exporter is not None:
            env["OTEL_LOGS_EXPORTER"] = logs_exporter
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
        assert "PROBE_DONE" in completed.stdout, completed.stdout
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=10)
    return list(_Recorder.paths)


def _free_port() -> int:
    import socket

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_logs_can_be_turned_off_while_traces_keep_exporting():
    """The documented escape hatch, asserted with its own control in the same run."""
    paths = _run_probe(_free_port(), logs_exporter="none")

    assert any(p.endswith("/v1/traces") for p in paths), (
        f"traces stopped exporting too, so the negative below proves nothing: {paths}"
    )
    assert not any(p.endswith("/v1/logs") for p in paths), f"log records were exported anyway: {paths}"


def test_logs_export_by_default_so_the_control_is_real():
    """Without the variable, logs do reach the endpoint.

    Without this, the test above passes on any build that never ships logs at all, which is the
    failure it is meant to detect.
    """
    paths = _run_probe(_free_port(), logs_exporter=None)

    assert any(p.endswith("/v1/logs") for p in paths), f"no log records exported by default: {paths}"

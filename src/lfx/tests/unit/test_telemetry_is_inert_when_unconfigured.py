"""With no OpenTelemetry configuration, nothing must leave the process.

An operator who has not opted into telemetry is entitled to assume none is produced and none
is sent. "No endpoint configured" is the default for every Langflow install, so this is the
common case rather than an edge one, and a regression here leaks to whatever happens to be
listening rather than failing loudly.

Three separate claims, because one does not imply the others:

* the global provider stays the API's no-op, so nothing is recorded
* no exporter threads are alive, so nothing is batching in the background
* nothing arrives at a listener on the default OTLP ports, so no hardcoded default endpoint
  is being used

The provider check is the one already covered elsewhere. A no-op provider does not prove some
other import path did not start an exporter thread of its own, which is why the other two are
here.

Runs in a subprocess with every OTEL_ variable stripped: the decision is made once per
process, and an inherited variable would decide the thing under test.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
from contextlib import closing, suppress
from pathlib import Path

import pytest

pytest.importorskip("opentelemetry.sdk.trace")

# The OTLP defaults. A listener here catches an exporter that was constructed with no endpoint
# and fell back to localhost.
OTLP_PORTS = (4317, 4318)

PROBE = """
import json, threading

# Captured before lfx is imported at all, so this is the API's own default. Comparing identity
# rather than checking "not an SDK provider": a custom provider that records and exports is
# neither the default nor an SDK type, so a type check would call that inert when it is not.
from opentelemetry import trace, metrics

default_tracer_provider = trace.get_tracer_provider()
default_meter_provider = metrics.get_meter_provider()

from lfx.observability import APPLICATION_METER_NAME, APPLICATION_TRACER_NAME, bootstrap_application_telemetry

telemetry = bootstrap_application_telemetry()

# Produce telemetry. If anything is live, this is what would be exported.
tracer = trace.get_tracer(APPLICATION_TRACER_NAME)
with tracer.start_as_current_span("flow.execute") as span:
    span.set_attribute("protocol", "probe")

meter = metrics.get_meter(APPLICATION_METER_NAME)
meter.create_counter("probe.counter").add(1)

# Enumerated BEFORE shutdown. Shutting down first stops the exporter threads, which made an
# earlier version of this report an empty list even with telemetry fully live.
otel_threads = sorted(t.name for t in threading.enumerate() if t.name.startswith("Otel"))

result = {
    "tracer_provider_unchanged": trace.get_tracer_provider() is default_tracer_provider,
    "meter_provider_unchanged": metrics.get_meter_provider() is default_meter_provider,
    "tracer_provider_type": type(trace.get_tracer_provider()).__name__,
    "meter_provider_type": type(metrics.get_meter_provider()).__name__,
    "otel_threads": otel_threads,
}

if telemetry is not None and getattr(telemetry, "shutdown", None):
    with __import__("contextlib").suppress(Exception):
        telemetry.shutdown()

print("PROBE_RESULT " + json.dumps(result))
"""


def _bind(port: int):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind(("127.0.0.1", port))
    except OSError:
        sock.close()
        return None
    sock.listen(8)
    sock.settimeout(0)
    return sock


def test_nothing_is_recorded_exported_or_sent_without_configuration():
    listeners = {port: _bind(port) for port in OTLP_PORTS}
    try:
        # Every port, not any: watching only one leaves a regression that connects to the other
        # undetected, and the test would report inertness it never checked. Inside the try so
        # the sockets that did bind are closed on the way out.
        unbound = sorted(port for port, sock in listeners.items() if sock is None)
        if unbound:
            pytest.skip(f"could not bind OTLP port(s) {unbound}; something else is using them")

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
        result = json.loads(line.removeprefix("PROBE_RESULT "))

        assert result["tracer_provider_unchanged"], (
            f"the global tracer provider was replaced with no endpoint set: {result['tracer_provider_type']}"
        )
        assert result["meter_provider_unchanged"], (
            f"the global meter provider was replaced with no endpoint set: {result['meter_provider_type']}"
        )
        assert result["otel_threads"] == [], f"exporter threads alive: {result['otel_threads']}"

        connected = []
        for port, sock in listeners.items():
            with suppress(BlockingIOError, OSError):
                conn, _ = sock.accept()
                conn.close()
                connected.append(port)
        assert connected == [], f"something connected to the OTLP default port(s): {connected}"
    finally:
        for sock in listeners.values():
            if sock is not None:
                with closing(sock):
                    pass

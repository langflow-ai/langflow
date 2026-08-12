"""Traceloop attaches to the global tracer provider, so it must not receive our own telemetry.

The Traceloop SDK takes no ``tracer_provider``. It adopts whichever provider is global and adds
its exporter to it, so when application observability is enabled it is *our* provider it attaches
to -- and its exporter then sees every span on it, including the service's own HTTP and flow
spans. Those belong in the operator's APM, which is not where Traceloop points.

Both the global provider and Traceloop's ``TracerWrapper`` are process-wide singletons that
cannot be undone in-process, so every case runs in its own subprocess against two real loopback
collectors. Span names are matched in the raw OTLP payload: counting requests is not enough,
because "one batch each" looks identical whether the split is correct or exactly inverted.
"""

import json
import os
import subprocess
import sys
import textwrap

import pytest

pytest.importorskip("traceloop.sdk", reason="requires the traceloop extra")

# Two loopback collectors standing in for the operator's APM and api.traceloop.com, plus the
# harness that reports which span names reached which one.
_HARNESS = """
import json, os, threading, time, uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

bodies = {"apm": [], "traceloop": []}

def _collector(which):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            bodies[which].append(body)
            self.send_response(200); self.send_header("Content-Length", "0"); self.end_headers()
        def log_message(self, *args):
            pass
    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server.server_port

apm_port, traceloop_port = _collector("apm"), _collector("traceloop")
os.environ["TRACELOOP_BASE_URL"] = f"http://127.0.0.1:{traceloop_port}"
os.environ["TRACELOOP_API_KEY"] = "test-key"  # pragma: allowlist secret

def report(**extra):
    time.sleep(1)
    seen = {}
    for target in ("apm", "traceloop"):
        seen[target] = sorted(
            name.decode()
            for name in (b"flow.execute", b"llm.call")
            if any(name in body for body in bodies[target])
        )
    print("RESULT " + json.dumps({**seen, **extra}))
"""


def _run(body: str) -> dict:
    # The probe sets every variable it depends on. An OTEL_ or TRACELOOP_ variable inherited
    # from the developer's shell (OTEL_TRACES_EXPORTER=none, OTEL_EXPORTER_OTLP_PROTOCOL=grpc)
    # would route the exporters away from the loopback collectors and fail all three.
    env = {k: v for k, v in os.environ.items() if not k.startswith(("OTEL_", "TRACELOOP_"))}
    completed = subprocess.run(  # noqa: S603
        [sys.executable, "-c", _HARNESS + textwrap.dedent(body)],
        capture_output=True,
        text=True,
        timeout=300,
        env=env,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr[-3000:]
    line = next((ln for ln in completed.stdout.splitlines() if ln.startswith("RESULT ")), None)
    assert line, f"probe printed no result:\n{completed.stdout[-2000:]}\n{completed.stderr[-2000:]}"
    return json.loads(line.removeprefix("RESULT "))


def test_application_spans_do_not_reach_the_llm_vendor():
    """The service's own telemetry must not be shipped to Traceloop's backend.

    Without the filter this fails with flow.execute present in BOTH lists: our provider fans
    out to the APM and to Traceloop, and only the APM leg is filtered.
    """
    result = _run("""
        os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = f"http://127.0.0.1:{apm_port}"
        os.environ["OTEL_TRACES_EXPORTER"] = "otlp"

        from lfx.observability import bootstrap_application_telemetry, APPLICATION_TRACER_NAME
        telemetry = bootstrap_application_telemetry(prometheus_enabled=False)

        from langflow.services.tracing.traceloop import TraceloopTracer
        tracer = TraceloopTracer(
            trace_name="probe", trace_type="chain", project_name="probe", trace_id=uuid.uuid4()
        )

        from opentelemetry import trace
        trace.get_tracer(APPLICATION_TRACER_NAME).start_span("flow.execute").end()
        telemetry.tracer_provider.force_flush(5000)
        report(ready=tracer._ready)
    """)

    assert result["ready"] is True, "the vendor integration must still initialise"
    assert result["apm"] == ["flow.execute"], "application telemetry belongs in the operator's APM"
    assert result["traceloop"] == [], "application telemetry leaked to the LLM vendor"


def test_application_spans_do_not_reach_the_vendor_without_an_apm():
    """The filter must also apply when no APM is configured, which is the common setup.

    With no OTLP endpoint the bootstrap installs nothing and the global provider is still a
    proxy. That does not mean there is nothing to filter: Traceloop then creates the concrete
    provider and registers it globally, the proxy resolves onto it, and the service's own spans
    reach the vendor by exactly the same route.
    """
    result = _run("""
        from lfx.observability import bootstrap_application_telemetry, APPLICATION_TRACER_NAME
        telemetry = bootstrap_application_telemetry(prometheus_enabled=False)

        from langflow.services.tracing.traceloop import TraceloopTracer
        tracer = TraceloopTracer(
            trace_name="probe", trace_type="chain", project_name="probe", trace_id=uuid.uuid4()
        )

        from opentelemetry import trace
        trace.get_tracer(APPLICATION_TRACER_NAME).start_span("flow.execute").end()
        report(ready=tracer._ready, installed=telemetry.tracer_provider is not None)
    """)

    assert result["installed"] is False, "no OTLP endpoint means the bootstrap installs no provider"
    assert result["ready"] is True, "the vendor integration must still initialise"
    assert result["traceloop"] == [], "application telemetry leaked to the LLM vendor"


def test_the_integration_is_disabled_when_the_filter_cannot_be_installed():
    """A future SDK that stops using the factory must break the integration, not the boundary.

    ``traceloop-sdk`` is depended on across a wide range, and the filter is installed by wrapping
    a function of theirs. If a release stops routing through it, nothing else changes: spans keep
    flowing and the only difference is that the service's own telemetry is in them. So a run that
    builds the SDK's pipeline without installing the filter has to fail loudly instead.

    Simulated by making the factory unreachable under the name the wrapper replaces, which is
    what any rename or inlining upstream would look like from here.
    """
    result = _run("""
        os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = f"http://127.0.0.1:{apm_port}"
        os.environ["OTEL_TRACES_EXPORTER"] = "otlp"

        from lfx.observability import bootstrap_application_telemetry, APPLICATION_TRACER_NAME
        telemetry = bootstrap_application_telemetry(prometheus_enabled=False)

        # Stand in for an upstream release that builds its exporter some other way: the name the
        # wrapper replaces is still there, but init no longer calls it.
        from traceloop.sdk.tracing import tracing as traceloop_tracing
        real = traceloop_tracing.get_default_span_processor
        traceloop_tracing.TracerWrapper.__new__ = (
            lambda cls, *a, **kw: object.__new__(cls) if not hasattr(cls, "instance") else cls.instance
        )

        from langflow.services.tracing.traceloop import TraceloopTracer
        tracer = TraceloopTracer(
            trace_name="probe", trace_type="chain", project_name="probe", trace_id=uuid.uuid4()
        )

        from opentelemetry import trace
        trace.get_tracer(APPLICATION_TRACER_NAME).start_span("flow.execute").end()
        telemetry.tracer_provider.force_flush(5000)
        report(ready=tracer.ready)
    """)

    assert result["ready"] is False, "the integration must refuse to run without the filter"
    assert result["traceloop"] == [], "application telemetry leaked to the LLM vendor"


def test_vendor_spans_still_reach_the_vendor():
    """Filtering our telemetry out must not cost Traceloop its own spans.

    The vendor span is emitted on the tracer TraceloopTracer itself uses ("langflow"), which is
    the scope the real integration puts flow content on and the nearest neighbour of the
    application allowlist. Asserted separately from the case above so a regression that
    silently drops everything cannot pass by looking like a successful filter.
    """
    result = _run("""
        os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = f"http://127.0.0.1:{apm_port}"
        os.environ["OTEL_TRACES_EXPORTER"] = "otlp"

        from lfx.observability import bootstrap_application_telemetry
        telemetry = bootstrap_application_telemetry(prometheus_enabled=False)

        from langflow.services.tracing.traceloop import TraceloopTracer
        TraceloopTracer(trace_name="probe", trace_type="chain", project_name="probe", trace_id=uuid.uuid4())

        from opentelemetry import trace
        trace.get_tracer("langflow").start_span("llm.call").end()
        telemetry.tracer_provider.force_flush(5000)
        report()
    """)

    assert result["traceloop"] == ["llm.call"], "the vendor must still receive its own spans"
    assert result["apm"] == [], "vendor spans must not reach the operator's APM"


def test_vendor_first_leaves_the_operator_without_application_telemetry():
    """Characterises the reverse order: no leak, but no application telemetry either.

    When Traceloop initialises before the bootstrap it claims the global provider, and OTel's
    set_tracer_provider is one-shot, so enabling OTLP afterwards in the same process cannot
    install ours. The operator's APM therefore receives nothing, and that part is a real
    limitation rather than something this change fixes.

    What it does fix is the direction that matters: the filter is on Traceloop's own processor,
    so it applies whichever provider Traceloop ended up with. The application span is dropped
    rather than shipped to the vendor.

    In practice the bootstrap runs at app startup and Traceloop only on the first flow run, so
    this ordering does not arise in a deployed process.
    """
    result = _run("""
        from langflow.services.tracing.traceloop import TraceloopTracer
        TraceloopTracer(trace_name="probe", trace_type="chain", project_name="probe", trace_id=uuid.uuid4())

        os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = f"http://127.0.0.1:{apm_port}"
        os.environ["OTEL_TRACES_EXPORTER"] = "otlp"
        from lfx.observability import bootstrap_application_telemetry, APPLICATION_TRACER_NAME
        telemetry = bootstrap_application_telemetry(prometheus_enabled=False)

        from opentelemetry import trace
        trace.get_tracer(APPLICATION_TRACER_NAME).start_span("flow.execute").end()
        report(installed=telemetry.tracer_provider is not None)
    """)

    assert result["installed"] is False, "the bootstrap must decline rather than fight for the global"
    assert result["apm"] == [], "known limitation: the APM receives nothing when the vendor initialises first"
    assert result["traceloop"] == [], "but application telemetry must still not reach the vendor"

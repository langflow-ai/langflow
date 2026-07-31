"""Enabling application observability must not disturb any LLM tracing vendor, or vice versa.

There is one global tracer provider per process and ``set_tracer_provider`` is one-shot, so a
vendor that registers itself globally takes the slot the application bootstrap needs -- and
then receives every span on it. That is exactly what happened in #13319, where Langfuse claimed
the global provider and FastAPIInstrumentor's HTTP spans started landing in Langfuse traces.

The vendors that are OpenTelemetry-based avoid this by building their own isolated provider
(``langfuse.py`` passes ``tracer_provider=``, ``langwatch.py`` sets
``skip_open_telemetry_setup=True``, ``arize_phoenix.py`` hands its provider to the
instrumentors). The four that are not OpenTelemetry-based have no provider at all. Either way
the property is the same and is what this pins: after constructing the vendor's tracer, the
global provider is still the object the bootstrap installed.

Traceloop is deliberately absent. It is the one vendor that does *not* hold this property -- it
adopts whichever provider is global -- and it has its own test file.

Each case runs in a subprocess: the global provider, and most of these vendors' clients, are
process-wide singletons that cannot be undone in-process.
"""

import importlib.util
import json
import os
import subprocess
import sys
import textwrap

import pytest

# Each vendor's endpoint is pointed at the loopback stub so nothing leaves the machine and no
# real credential is needed. ``provider_expr`` is evaluated against the constructed tracer for
# the vendors that expose their own provider, to pin that it is a *different* object from the
# global one rather than merely absent.
_VENDORS = {
    "arize_phoenix": {
        "requires": "phoenix",
        "module": "langflow.services.tracing.arize_phoenix",
        "cls": "ArizePhoenixTracer",
        "env": {
            "PHOENIX_API_KEY": "probe-key",  # pragma: allowlist secret
            "PHOENIX_COLLECTOR_ENDPOINT": "http://127.0.0.1:{vendor_port}",
        },
        "provider_expr": "tracer.tracer_provider",
    },
    "langfuse": {
        "requires": "langfuse",
        "module": "langflow.services.tracing.langfuse",
        "cls": "LangFuseTracer",
        "env": {
            "LANGFUSE_SECRET_KEY": "sk-probe",  # pragma: allowlist secret
            "LANGFUSE_PUBLIC_KEY": "pk-probe",  # pragma: allowlist secret
            "LANGFUSE_BASE_URL": "http://127.0.0.1:{vendor_port}",
        },
        # The isolated provider is held inside the shared Langfuse client, so there is no
        # accessor on the tracer. "the global provider is untouched" is the #13319 property.
        "provider_expr": None,
    },
    "langsmith": {
        "requires": "langsmith",
        "module": "langflow.services.tracing.langsmith",
        "cls": "LangSmithTracer",
        "env": {
            "LANGCHAIN_API_KEY": "probe-key",  # pragma: allowlist secret
            "LANGCHAIN_ENDPOINT": "http://127.0.0.1:{vendor_port}",
        },
        "provider_expr": None,
    },
    "langsmith_otel": {
        "requires": "langsmith",
        "module": "langflow.services.tracing.langsmith",
        "cls": "LangSmithTracer",
        "env": {
            "LANGCHAIN_API_KEY": "probe-key",  # pragma: allowlist secret
            "LANGCHAIN_ENDPOINT": "http://127.0.0.1:{vendor_port}",
            "LANGSMITH_TRACING_MODE": "otel",
        },
        "provider_expr": None,
    },
    "langsmith_hybrid": {
        "requires": "langsmith",
        "module": "langflow.services.tracing.langsmith",
        "cls": "LangSmithTracer",
        "env": {
            "LANGCHAIN_API_KEY": "probe-key",  # pragma: allowlist secret
            "LANGCHAIN_ENDPOINT": "http://127.0.0.1:{vendor_port}",
            "LANGSMITH_TRACING_MODE": "hybrid",
        },
        "provider_expr": None,
    },
    "langwatch": {
        "requires": "langwatch",
        "module": "langflow.services.tracing.langwatch",
        "cls": "LangWatchTracer",
        "env": {
            "LANGWATCH_API_KEY": "probe-key",  # pragma: allowlist secret
            "LANGWATCH_ENDPOINT": "http://127.0.0.1:{vendor_port}",
        },
        "provider_expr": "type(tracer).tracer_provider",
    },
    "openlayer": {
        "requires": "openlayer",
        "module": "langflow.services.tracing.openlayer",
        "cls": "OpenlayerTracer",
        "env": {
            "OPENLAYER_API_KEY": "probe-key",  # pragma: allowlist secret
            "OPENLAYER_INFERENCE_PIPELINE_ID": "probe-pipeline",
            "OPENLAYER_BASE_URL": "http://127.0.0.1:{vendor_port}",
        },
        "provider_expr": None,
    },
    "opik": {
        "requires": "opik",
        "module": "langflow.services.tracing.opik",
        "cls": "OpikTracer",
        "env": {
            "OPIK_API_KEY": "probe-key",  # pragma: allowlist secret
            "OPIK_WORKSPACE": "probe-workspace",
            "OPIK_URL_OVERRIDE": "http://127.0.0.1:{vendor_port}/api",
        },
        "provider_expr": None,
    },
}

# Two loopback servers: one standing in for the operator's APM, one for the vendor's backend.
# The vendor stub answers Langfuse's auth_check (GET /api/public/projects, whose response it
# validates against a model) and returns an empty JSON object to everything else, which is
# enough for every other vendor's client to consider itself initialised.
_HARNESS = """
import json, os, threading, time, uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

bodies = {"apm": [], "vendor": []}

def _collector(which):
    class Handler(BaseHTTPRequestHandler):
        def _respond(self):
            length = int(self.headers.get("Content-Length", 0) or 0)
            bodies[which].append(self.rfile.read(length))
            if "/api/public/projects" in self.path:
                payload = json.dumps({"data": [{
                    "id": "probe", "name": "probe", "metadata": {},
                    "organization": {"id": "probe-org", "name": "probe-org", "metadata": {}},
                }]}).encode()
            else:
                payload = b"{}"
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        do_POST = do_GET = do_PUT = do_PATCH = _respond
        def log_message(self, *args):
            pass
    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server.server_port

apm_port, vendor_port = _collector("apm"), _collector("vendor")

def report(**extra):
    time.sleep(1)
    print("RESULT " + json.dumps({
        "vendor_saw_application_span": any(b"flow.execute" in body for body in bodies["vendor"]),
        "apm_saw_application_span": any(b"flow.execute" in body for body in bodies["apm"]),
        **extra,
    }))
"""

_SETUP = """
import importlib

for key, value in {env!r}.items():
    os.environ[key] = value.format(vendor_port=vendor_port)

os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = f"http://127.0.0.1:{{apm_port}}"
os.environ["OTEL_TRACES_EXPORTER"] = "otlp"

from lfx.observability import bootstrap_application_telemetry, APPLICATION_TRACER_NAME
from opentelemetry import trace

def build_vendor_tracer():
    return getattr(importlib.import_module({module!r}), {cls!r})(
        "probe - 00000000-0000-0000-0000-000000000000", "chain", "probe", uuid.uuid4()
    )
"""

# The vendor initialises first and the bootstrap runs after it. This is the order in which the
# global provider slot is actually contested: set_tracer_provider is one-shot, so a vendor that
# claims it leaves the bootstrap with nowhere to install and the operator with no telemetry.
_PROBE_VENDOR_FIRST = """
tracer = build_vendor_tracer()
telemetry = bootstrap_application_telemetry(prometheus_enabled=False)

vendor_provider = {provider_expr}

report(
    ready=bool(tracer.ready),
    bootstrap_installed=telemetry.tracer_provider is not None,
    bootstrap_owns_global=trace.get_tracer_provider() is telemetry.tracer_provider,
    vendor_provider_is_separate=(vendor_provider is not trace.get_tracer_provider())
    if vendor_provider is not None
    else None,
    has_vendor_provider=vendor_provider is not None,
)
"""

# The bootstrap initialises first, which is the real deployment order: it runs at app startup
# and a vendor tracer is only built on the first flow run.
_PROBE_BOOTSTRAP_FIRST = """
telemetry = bootstrap_application_telemetry(prometheus_enabled=False)
tracer = build_vendor_tracer()

trace.get_tracer(APPLICATION_TRACER_NAME).start_span("flow.execute").end()
telemetry.tracer_provider.force_flush(5000)

report(ready=bool(tracer.ready))
"""


def _run(vendor: str, probe: str) -> dict:
    spec = _VENDORS[vendor]
    body = _SETUP.format(env=spec["env"], module=spec["module"], cls=spec["cls"]) + probe.format(
        provider_expr=spec["provider_expr"] or "None"
    )
    # The probe sets every variable it depends on. Inherited OTEL_ or vendor variables from the
    # developer's shell (OTEL_TRACES_EXPORTER=none, a real LANGFUSE_HOST) would route exporters
    # away from the loopback stubs or point a client at a real backend.
    prefixes = ("OTEL_", "LANGFUSE_", "LANGCHAIN_", "LANGSMITH_", "LANGWATCH_", "PHOENIX_", "ARIZE_")
    prefixes += ("OPENLAYER_", "OPIK_", "COMET_", "TRACELOOP_")
    env = {k: v for k, v in os.environ.items() if not k.startswith(prefixes)}
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


def _vendor_params():
    """Skip a vendor whose SDK is not installed here rather than failing the ready guard.

    ``langwatch`` is declared ``python_version < "3.14"``, so on 3.14 it is legitimately
    absent and its tracer can never report ready.
    """
    for name in sorted(_VENDORS):
        missing = importlib.util.find_spec(_VENDORS[name]["requires"]) is None
        marks = [pytest.mark.skip(reason=f"{_VENDORS[name]['requires']} is not installed")] if missing else []
        yield pytest.param(name, marks=marks)


@pytest.mark.parametrize("vendor", _vendor_params())
def test_vendor_does_not_claim_the_global_provider(vendor: str):
    """A vendor that initialises first must still leave the global slot for the bootstrap.

    Traceloop fails this one, which is why it is not in the table: it claims the global
    provider, and because ``set_tracer_provider`` is one-shot the bootstrap then cannot install
    and the operator's APM receives nothing.

    ``ready`` is asserted first and deliberately: a vendor that failed to initialise would leave
    the global slot free for the trivial reason that it did nothing, and every other assertion
    here would pass while pinning nothing.
    """
    result = _run(vendor, _PROBE_VENDOR_FIRST)

    assert result["ready"] is True, f"{vendor} did not initialise, so this case pins nothing"
    assert result["bootstrap_installed"] is True, f"{vendor} claimed the global provider, leaving the APM with none"
    assert result["bootstrap_owns_global"] is True, f"the global provider is not the bootstrap's after {vendor}"
    if result["has_vendor_provider"]:
        assert result["vendor_provider_is_separate"] is True, f"{vendor} is exporting from the global provider"


@pytest.mark.parametrize("vendor", _vendor_params())
def test_application_spans_do_not_reach_the_vendor(vendor: str):
    """The operator's application telemetry must stay out of the vendor's backend.

    This is the assertion that catches #13319, and it is not implied by the one above. Reverting
    that fix leaves the global provider's *identity* untouched -- the SDK cannot replace a
    provider that is already set -- while its exporter still attaches to ours and starts
    receiving the service's own spans. Identity and export are separate properties.
    """
    result = _run(vendor, _PROBE_BOOTSTRAP_FIRST)

    assert result["ready"] is True, f"{vendor} did not initialise, so this case pins nothing"
    assert result["apm_saw_application_span"] is True, "the APM must receive the application span"
    assert result["vendor_saw_application_span"] is False, f"application telemetry leaked to {vendor}"

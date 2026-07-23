"""Application observability works from lfx alone, with no langflow import.

This is the point of the module living in lfx: ``lfx serve`` and ``lfx run`` are the production
runtime, so the provider bootstrap and the export boundary must be reachable and correct
without the full langflow app. The subprocess probes import only ``lfx.observability``.

OpenTelemetry is an optional lfx extra (``lfx[otel]``), so bare lfx installs it without otel.
The first test asserts that path stays a safe no-op; the rest need the exporters and skip when
the extra is absent.
"""

import importlib.util
import json
import os
import subprocess
import sys

import pytest

_HAS_OTEL = importlib.util.find_spec("opentelemetry") is not None
requires_otel = pytest.mark.skipif(not _HAS_OTEL, reason="requires the lfx[otel] extra")


def _run(probe: str, env_overrides: dict[str, str]) -> subprocess.CompletedProcess:
    # Start from a clean slate so the developer's own OTEL_* vars cannot skew the result.
    env = {k: v for k, v in os.environ.items() if not k.startswith("OTEL_")}
    env.update(env_overrides)
    return subprocess.run(  # noqa: S603
        [sys.executable, "-c", probe],
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )


def test_bootstrap_is_safe_without_endpoint_or_otel():
    """Bootstrap must import and no-op without otel and without an endpoint.

    This probe imports ONLY lfx.observability -- never opentelemetry -- so it runs whether or
    not the otel extra is installed, and proves the guarded no-op path bare lfx relies on.
    """
    probe = (
        "from lfx.observability import bootstrap_application_telemetry, ApplicationTelemetry\n"
        "result = bootstrap_application_telemetry(prometheus_enabled=False)\n"
        "assert isinstance(result, ApplicationTelemetry)\n"
        "assert result.tracer_provider is None  # no endpoint -> nothing installed\n"
        "print('BOOTSTRAP_OK')\n"
    )
    completed = _run(probe, {})
    assert completed.returncode == 0, completed.stderr
    assert "BOOTSTRAP_OK" in completed.stdout


# Forces the no-otel condition by blocking the opentelemetry import, so it exercises the real
# bare-lfx path whether or not the extra is installed in this environment.
_NO_OTEL_PROBE = (
    "import sys\n"
    "class _Block:\n"
    "    def find_spec(self, name, path=None, target=None):\n"
    "        if name == 'opentelemetry' or name.startswith('opentelemetry.'):\n"
    "            raise ImportError('blocked')\n"
    "        return None\n"
    "sys.meta_path.insert(0, _Block())\n"
    "from lfx.log.logger import configure\n"
    "configure(log_level='WARNING')\n"
    "from lfx.observability import bootstrap_application_telemetry\n"
    "bootstrap_application_telemetry()\n"
)


def test_endpoint_without_otel_warns_and_points_at_the_extra():
    """An endpoint set without the otel extra must warn and name the install.

    Otherwise it is a silent-export trap: nothing exports and nothing says why, so the operator
    cannot tell whether the endpoint is wrong or the dependency is missing.
    """
    completed = _run(_NO_OTEL_PROBE, {"OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4318"})
    assert completed.returncode == 0, completed.stderr
    assert "lfx[otel]" in completed.stdout + completed.stderr


def test_no_endpoint_without_otel_stays_silent():
    """Bare lfx with no endpoint is the default install; it must not nag about a missing extra."""
    completed = _run(_NO_OTEL_PROBE, {})
    assert completed.returncode == 0, completed.stderr
    assert "lfx[otel]" not in completed.stdout + completed.stderr


def test_shutdown_without_providers_is_a_noop():
    """Empty handles (nothing configured, or otel absent) must shut down without error.

    Imports only lfx.observability, so it runs whether or not the otel extra is installed.
    """
    from lfx.observability import ApplicationTelemetry

    ApplicationTelemetry().shutdown()


@requires_otel
def test_shutdown_flushes_buffered_spans():
    """shutdown() must flush the batch processor. Without it the last spans drop on exit.

    uvicorn and gunicorn die by signal and never run the SDK's atexit flush, so an explicit
    shutdown is the only thing that gets the in-flight batch out on restart and pod eviction.
    """
    from lfx.observability import ApplicationTelemetry
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    # A long delay so nothing exports on its own timer: only the flush inside shutdown() sends it.
    provider.add_span_processor(BatchSpanProcessor(exporter, schedule_delay_millis=600_000))
    provider.get_tracer("t").start_span("s").end()
    assert exporter.get_finished_spans() == (), "span should still be buffered before shutdown"

    ApplicationTelemetry(tracer_provider=provider).shutdown()
    assert [span.name for span in exporter.get_finished_spans()] == ["s"]


# Installs a process-global tracer provider, so anything touching env-driven installation runs
# in a subprocess. The probe imports only lfx.observability -- if that quietly needed langflow,
# these would fail to import.
_PROVIDER_PROBE = """
import json
from lfx.observability import bootstrap_application_telemetry
from opentelemetry import trace

result = bootstrap_application_telemetry(prometheus_enabled=False)
provider = trace.get_tracer_provider()
out = {"provider": type(provider).__name__, "tracer_provider_returned": result.tracer_provider is not None}
processors = getattr(getattr(provider, "_active_span_processor", None), "_span_processors", ())
out["processors"] = [type(p).__name__ for p in processors]
resource = getattr(provider, "resource", None)
if resource is not None:
    out["service_name"] = resource.attributes.get("service.name")
print("PROBE_RESULT " + json.dumps(out))
"""


def _run_provider_probe(env_overrides: dict[str, str]) -> dict:
    completed = _run(_PROVIDER_PROBE, env_overrides)
    assert completed.returncode == 0, completed.stderr
    line = next(ln for ln in completed.stdout.splitlines() if ln.startswith("PROBE_RESULT "))
    return json.loads(line.removeprefix("PROBE_RESULT "))


@requires_otel
def test_no_endpoint_installs_no_provider():
    """No OTEL_* env means no export, from lfx just as from langflow."""
    result = _run_provider_probe({})
    assert result["provider"] == "ProxyTracerProvider"
    assert result["tracer_provider_returned"] is False


@requires_otel
@pytest.mark.parametrize("endpoint_var", ["OTEL_EXPORTER_OTLP_ENDPOINT", "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"])
def test_endpoint_installs_filtered_provider(endpoint_var):
    """An endpoint installs a real provider whose processor is the application-only filter."""
    result = _run_provider_probe({endpoint_var: "http://localhost:4318"})
    assert result["provider"] == "TracerProvider"
    assert result["tracer_provider_returned"] is True
    assert "ApplicationOnlySpanProcessor" in result["processors"]
    assert result["service_name"] == "langflow"


@requires_otel
def test_traces_exporter_none_disables_export():
    """OTEL_TRACES_EXPORTER=none turns traces off even with a shared endpoint set."""
    result = _run_provider_probe(
        {"OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4318", "OTEL_TRACES_EXPORTER": "none"},
    )
    assert result["provider"] == "ProxyTracerProvider"


@requires_otel
def test_span_filter_drops_llm_scopes():
    """The export boundary: application spans pass, LLM-instrumentation spans are dropped.

    In-process because it wires its own provider with an in-memory exporter rather than
    installing the global one.
    """
    from lfx.observability import APPLICATION_TRACER_NAME, ApplicationOnlySpanProcessor
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(ApplicationOnlySpanProcessor(exporter))

    # An application span (allowlisted scope) and an LLM-instrumentation span (carries prompts).
    provider.get_tracer(APPLICATION_TRACER_NAME).start_span("flow.execute").end()
    provider.get_tracer("opentelemetry.instrumentation.openai").start_span("openai.chat").end()
    provider.force_flush()

    exported = {span.name for span in exporter.get_finished_spans()}
    assert exported == {"flow.execute"}


@requires_otel
def test_instrument_fastapi_app_sets_stable_semconv():
    """The shared FastAPI helper opts into the stable HTTP conventions before instrumenting."""
    os.environ.pop("OTEL_SEMCONV_STABILITY_OPT_IN", None)
    from fastapi import FastAPI
    from lfx.observability import instrument_fastapi_app

    instrument_fastapi_app(FastAPI())
    assert os.environ.get("OTEL_SEMCONV_STABILITY_OPT_IN") == "http"

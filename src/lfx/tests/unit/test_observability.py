"""Application observability works from lfx alone, with no langflow import.

This is the point of the module living in lfx: ``lfx serve`` and ``lfx run`` are the production
runtime, so the provider bootstrap and the export boundary must be reachable and correct
without the full langflow app. The subprocess probes import only ``lfx.observability``.
"""

import json
import os
import subprocess
import sys

import pytest

# Installs a process-global tracer provider, so anything touching env-driven installation runs
# in a subprocess. The probe imports ONLY lfx.observability -- if that quietly needed langflow,
# this would fail to import.
PROBE = """
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


def _run_probe(env_overrides: dict[str, str]) -> dict:
    # Start from a clean slate so the developer's own OTEL_* vars cannot skew the result.
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


def test_no_endpoint_installs_no_provider():
    """No OTEL_* env means no export, from lfx just as from langflow."""
    result = _run_probe({})
    assert result["provider"] == "ProxyTracerProvider"
    assert result["tracer_provider_returned"] is False


@pytest.mark.parametrize("endpoint_var", ["OTEL_EXPORTER_OTLP_ENDPOINT", "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"])
def test_endpoint_installs_filtered_provider(endpoint_var):
    """An endpoint installs a real provider whose processor is the application-only filter."""
    result = _run_probe({endpoint_var: "http://localhost:4318"})
    assert result["provider"] == "TracerProvider"
    assert result["tracer_provider_returned"] is True
    assert "ApplicationOnlySpanProcessor" in result["processors"]
    assert result["service_name"] == "langflow"


def test_traces_exporter_none_disables_export():
    """OTEL_TRACES_EXPORTER=none turns traces off even with a shared endpoint set."""
    result = _run_probe(
        {"OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4318", "OTEL_TRACES_EXPORTER": "none"},
    )
    assert result["provider"] == "ProxyTracerProvider"


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


def test_instrument_fastapi_app_sets_stable_semconv():
    """The shared FastAPI helper opts into the stable HTTP conventions before instrumenting."""
    os.environ.pop("OTEL_SEMCONV_STABILITY_OPT_IN", None)
    from fastapi import FastAPI
    from lfx.observability import instrument_fastapi_app

    instrument_fastapi_app(FastAPI())
    assert os.environ.get("OTEL_SEMCONV_STABILITY_OPT_IN") == "http"

"""Langflow's own metrics must not follow a provider someone else registers later.

In the default deployment shape — no OTLP endpoint, Prometheus off — the bootstrap declines to
install a MeterProvider. The service then has to record its metrics somewhere, and the obvious
somewhere is the global API provider.

That is a trap. The global provider at that moment is a *proxy*, and a proxy meter is not a
no-op: its instruments resolve lazily onto whichever real MeterProvider is registered
afterwards. An LLM tracing SDK that registers one on the first flow run therefore adopts every
metric Langflow records, labels included, and ships it to the vendor's endpoint.

The allowlist that draws this boundary for the OTLP exporter cannot help: it is applied to the
exporter Langflow owns, and this path never goes through it.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from langflow.services.telemetry.opentelemetry import OpenTelemetry
from lfx.observability_llm_metrics import LLMProviderMetricsCallbackHandler
from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader


def _recorded_by_a_late_provider(record) -> list[str]:
    """Register a real provider AFTER the service, the way a tracing SDK does, and see what lands."""
    reader = InMemoryMetricReader()
    metrics.set_meter_provider(MeterProvider(metric_readers=[reader]))
    record()
    data = reader.get_metrics_data()
    return [
        metric.name
        for rm in (data.resource_metrics if data else [])
        for sm in rm.scope_metrics
        for metric in sm.metrics
    ]


def test_metrics_do_not_follow_a_provider_registered_after_startup():
    """The regression. Nothing Langflow records may reach a provider it did not choose.

    Every path that builds an instrument is exercised in this one test on purpose:
    ``set_meter_provider`` is one-shot, so a second test calling it would keep the provider
    this one registered and assert against a reader nothing was ever wired to. One
    registration, every recorder.

    The three paths reached the global API separately, so fixing one left the others leaking:
    the counters and histograms take the service's own meter, the observable gauges built
    their own, and the LLM provider metrics live in lfx and build a third.
    """
    service = OpenTelemetry(prometheus_enabled=False)
    llm_metrics = LLMProviderMetricsCallbackHandler()

    def record_from_every_path() -> None:
        service.increment_counter("num_files_uploaded", labels={"flow_id": "probe-flow"}, value=3)
        service.update_gauge("file_uploads", value=4242.0, labels={"flow_id": "probe-flow"})
        llm_metrics._duration.record(1.5, {"gen_ai.system": "openai", "gen_ai.request.model": "probe"})
        llm_metrics._errors.add(1, {"error.type": "ProbeError"})

    landed = _recorded_by_a_late_provider(record_from_every_path)

    assert landed == [], f"Langflow metrics reached a provider registered by someone else: {landed}"


def test_recording_a_metric_still_works_when_nothing_is_configured():
    """The control. The fix must make the metric go nowhere, not make recording raise.

    Without this, returning a broken meter would pass the test above for the wrong reason and
    take the whole service down on the first upload.
    """
    service = OpenTelemetry(prometheus_enabled=False)

    service.increment_counter("num_files_uploaded", labels={"flow_id": "probe-flow"}, value=1)


CONFIGURED_PROBE = """
from langflow.services.telemetry.opentelemetry import OpenTelemetry
from lfx.observability_llm_metrics import get_llm_provider_metrics_handler

service = OpenTelemetry(prometheus_enabled=True)
handler = get_llm_provider_metrics_handler()
print("PROBE_RESULT " + repr({
    "owns_provider": service._meter_provider is not None,
    "meter_type": type(service.meter).__name__,
    "gauge_meter_type": type(service._metrics["file_uploads"]._meter).__name__,
    "llm_instrument_type": type(handler._duration).__name__,
}))
"""


def test_a_configured_provider_still_receives_the_metrics():
    """The other control, and the one that stops this fix going too far.

    Silencing the unconfigured case is only correct if the configured case is untouched. With
    Prometheus on, the bootstrap installs a provider Langflow owns, and the metrics belong on
    it. A fix that made every meter a no-op would pass the first test and quietly delete the
    feature.

    Runs in a subprocess: ``set_meter_provider`` is one-shot, and the tests above deliberately
    register a provider, so in-process this would assert against whichever ran first.
    """
    env = {k: v for k, v in os.environ.items() if not k.startswith("OTEL_")}
    with tempfile.TemporaryDirectory() as tmp:
        probe = Path(tmp) / "probe.py"
        probe.write_text(CONFIGURED_PROBE, encoding="utf-8")
        completed = subprocess.run(  # noqa: S603
            [sys.executable, str(probe)], env=env, capture_output=True, text=True, timeout=300, check=False
        )
    assert completed.returncode == 0, completed.stderr
    line = next(ln for ln in completed.stdout.splitlines() if ln.startswith("PROBE_RESULT "))
    result = ast.literal_eval(line.removeprefix("PROBE_RESULT "))

    assert result["owns_provider"], "the bootstrap should own a provider when Prometheus is on"
    assert result["meter_type"] != "NoOpMeter", "a configured deployment must still record"
    assert result["gauge_meter_type"] != "NoOpMeter", "the gauges must record too, not just the counters"
    assert result["llm_instrument_type"] != "NoOpHistogram", "the LLM provider metrics must record too"

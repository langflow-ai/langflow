"""Application observability works from lfx alone, with no langflow import.

This is the point of the module living in lfx: ``lfx serve`` and ``lfx run`` are the production
runtime, so the provider bootstrap and the export boundary must be reachable and correct
without the full langflow app. The subprocess probes import only ``lfx.observability``.

OpenTelemetry is an optional lfx extra (``lfx[otel]``), so bare lfx installs it without otel.
The first test asserts that path stays a safe no-op; the rest need the exporters and skip when
the extra is absent.
"""

import builtins
import importlib.util
import json
import os
import subprocess
import sys

import httpx
import pytest

_HAS_OTEL = importlib.util.find_spec("opentelemetry") is not None
requires_otel = pytest.mark.skipif(not _HAS_OTEL, reason="requires the lfx[otel] extra")
_TEST_USERINFO = "user:password"  # pragma: allowlist secret


def _make_exception_group(message: str, exceptions: list[Exception]) -> BaseException:
    group_type = getattr(builtins, "ExceptionGroup", None)
    if group_type is None:
        group_type = pytest.importorskip("exceptiongroup").ExceptionGroup
    return group_type(message, exceptions)


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


def _export_application_span(attributes, *, span_limits=None):
    from lfx.observability import APPLICATION_TRACER_NAME, ApplicationOnlySpanProcessor
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exporter = InMemorySpanExporter()
    provider = TracerProvider(span_limits=span_limits)
    provider.add_span_processor(ApplicationOnlySpanProcessor(exporter))
    try:
        span = provider.get_tracer(APPLICATION_TRACER_NAME).start_span("url.redaction")
        for key, value in attributes.items():
            span.set_attribute(key, value)
        span.end()
        provider.force_flush()
        exported = exporter.get_finished_spans()
    finally:
        provider.shutdown()

    assert len(exported) == 1
    return exported[0]


@requires_otel
@pytest.mark.parametrize(
    ("attribute", "value", "expected"),
    [
        ("url.query", "x-api-key=secret", ""),
        ("http.target", "/flows/run?x-api-key=secret#fragment", "/flows/run"),
        (
            "url.full",
            f"https://{_TEST_USERINFO}@example.com:443/flows/run?x-api-key=secret#fragment",
            "https://example.com:443/flows/run",
        ),
        (
            "http.url",
            f"http://{_TEST_USERINFO}@[2001:db8::1]:0/flows/run?x-api-key=secret#fragment",
            "http://[2001:db8::1]:0/flows/run",
        ),
        (
            "http.url",
            f"http://{_TEST_USERINFO}@example.com:notaport/flows/run?x-api-key=secret#fragment",
            "",
        ),
        ("url.full", "http://[broken/flows/run?x-api-key=secret", ""),
        ("url.full", f"http:{_TEST_USERINFO}@example.com/flows/run?x-api-key=secret", ""),
        ("http.url", f"http:///{_TEST_USERINFO}@example.com/flows/run?x-api-key=secret", ""),
        ("http.target", f"http:{_TEST_USERINFO}@example.com/flows/run?x-api-key=secret", ""),
        ("url.full", (f"https://{_TEST_USERINFO}@example.com/flows/run?x-api-key=secret",), ""),
    ],
)
def test_span_filter_redacts_url_attributes_without_losing_operational_details(attribute, value, expected):
    span_attributes = {attribute: value, "http.request.method": "GET"}
    if attribute != "url.query":
        span_attributes["url.query"] = "another-secret=x"
    exported = _export_application_span(span_attributes)

    assert exported.attributes[attribute] == expected
    if attribute != "url.query":
        assert exported.attributes["url.query"] == ""
    assert exported.attributes["http.request.method"] == "GET"
    assert "secret" not in str(exported.attributes)
    assert "password" not in str(exported.attributes)


@requires_otel
def test_span_filter_preserves_attribute_limits_and_drop_count():
    from opentelemetry.sdk.trace import SpanLimits

    exported = _export_application_span(
        {"discarded": "value", "url.full": "https://secret@example.com/flows/run?secret=x"},
        span_limits=SpanLimits(max_span_attributes=1, max_span_attribute_length=14),
    )

    assert exported.attributes["url.full"] == ""
    assert exported.dropped_attributes == 1
    assert exported._attributes.maxlen == 1
    assert exported._attributes.max_value_len == 14


def test_root_error_type_unwraps_a_single_exception_group():
    from lfx.observability import _root_error_type

    connection_error = httpx.ConnectError("server unavailable")
    error_group = _make_exception_group("MCP transport failed", [connection_error])

    assert _root_error_type(error_group) == "ConnectError"


def test_root_error_type_keeps_a_multi_exception_group():
    from lfx.observability import _root_error_type

    error_group = _make_exception_group("MCP transport failed", [ConnectionError(), TimeoutError()])

    assert _root_error_type(error_group) == "ExceptionGroup"


@requires_otel
@pytest.mark.parametrize(
    ("env_overrides", "expected"),
    [
        pytest.param({}, "http", id="default"),
        pytest.param({"OTEL_SEMCONV_STABILITY_OPT_IN": "http/dup"}, "http/dup", id="operator-override"),
    ],
)
def test_importing_observability_opts_into_stable_semconv(env_overrides: dict[str, str], expected: str):
    """The opt-in happens at import, which is the only point early enough.

    It used to live in ``instrument_fastapi_app``. That reads as early enough and is not:
    ``bootstrap_application_telemetry`` runs first on both runtimes and loads OpenTelemetry's
    instrumentation package, which caches the decision for the process while the variable is
    still unset. Popping the variable and re-calling the helper cannot restore the old
    behaviour, because the cache is already set by then.

    Each case runs in a subprocess because the import and the OpenTelemetry decision are both
    process-wide. The default is stable-only, while an operator can request both conventions
    during a dashboard migration.
    """
    probe = "import os\nimport lfx.observability\nprint(os.environ['OTEL_SEMCONV_STABILITY_OPT_IN'])\n"
    completed = _run(probe, env_overrides)

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == expected


@requires_otel
def test_no_readers_installs_no_meter_provider():
    """Bare serve (no endpoint, Prometheus off) must not install a reader-less global provider.

    set_meter_provider is first-write-wins, so a reader-less provider would block one a later
    integration installs while exporting nothing; the traces and logs paths decline the same way.
    """
    probe = (
        "from lfx.observability import bootstrap_application_telemetry\n"
        "from opentelemetry import metrics\n"
        "from opentelemetry.sdk.metrics import MeterProvider\n"
        "result = bootstrap_application_telemetry(prometheus_enabled=False)\n"
        "installed = isinstance(metrics.get_meter_provider(), MeterProvider)\n"
        "print('METER', result.meter_provider is None, result.owns_meter_provider, installed)\n"
    )
    completed = _run(probe, {})
    assert completed.returncode == 0, completed.stderr
    assert "METER True False False" in completed.stdout


@requires_otel
def test_shutdown_leaves_an_adopted_meter_provider_alone():
    """A provider adopted from another integration is not ours to shut down.

    Shutting it down here would tear down the host's metrics pipeline in an embedded or
    in-process-restart scenario.
    """
    from lfx.observability import ApplicationTelemetry
    from opentelemetry.sdk.metrics import MeterProvider

    foreign = MeterProvider()
    # owns_meter_provider defaults False -> adopted.
    ApplicationTelemetry(meter_provider=foreign).shutdown()
    assert foreign._shutdown is False, "adopted provider must be left running"


@requires_otel
def test_shutdown_shuts_down_a_meter_provider_we_own():
    """A provider this bootstrap installed is flushed and shut down on exit."""
    from lfx.observability import ApplicationTelemetry
    from opentelemetry.sdk.metrics import MeterProvider

    owned = MeterProvider()
    ApplicationTelemetry(meter_provider=owned, owns_meter_provider=True).shutdown()
    assert owned._shutdown is True


def test_event_loop_lag_monitor_is_a_noop_without_a_provider():
    """Nothing configured means nothing to record on, and no stray task."""
    from lfx.observability import start_event_loop_lag_monitor

    assert start_event_loop_lag_monitor(None) is None


async def test_stop_event_loop_lag_monitor_preserves_caller_cancellation():
    """Stopping the monitor must not consume cancellation of the lifespan task."""
    import asyncio

    from lfx.observability import stop_event_loop_lag_monitor

    async def monitor():
        await asyncio.Event().wait()

    monitor_task = asyncio.create_task(monitor())
    await asyncio.sleep(0)

    async def stop_from_cancelled_caller():
        asyncio.current_task().cancel()
        await stop_event_loop_lag_monitor(monitor_task)

    caller_task = asyncio.create_task(stop_from_cancelled_caller())
    with pytest.raises(asyncio.CancelledError):
        await caller_task

    assert caller_task.cancelled()
    assert monitor_task.cancelled()


@requires_otel
async def test_event_loop_lag_monitor_records_a_blocked_loop():
    """The point of the metric: a blocked loop must show up as lag.

    Blocks the loop thread with a synchronous sleep, which is exactly the failure this
    exists to catch (a sync call in a component), and asserts the sampler noticed. Uses a
    real MeterProvider and reader rather than a mock, so it fails if the instrument is
    misconfigured, not just if the arithmetic is wrong.
    """
    import asyncio
    import time as _time

    from lfx.observability import EVENT_LOOP_LAG_METRIC, start_event_loop_lag_monitor, stop_event_loop_lag_monitor
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import InMemoryMetricReader

    reader = InMemoryMetricReader()
    provider = MeterProvider(metric_readers=[reader], shutdown_on_exit=False)

    task = start_event_loop_lag_monitor(provider, interval=0.01)
    assert task is not None
    await asyncio.sleep(0.05)
    # Blocking the loop is the whole point of this test: it is the failure the metric exists
    # to catch, so the lint that forbids it in async code is exactly what we are simulating.
    _time.sleep(0.3)  # noqa: ASYNC251
    await asyncio.sleep(0.05)
    await stop_event_loop_lag_monitor(task)

    points = [
        point
        for rm in (reader.get_metrics_data().resource_metrics or [])
        for sm in rm.scope_metrics
        for metric in sm.metrics
        if metric.name == EVENT_LOOP_LAG_METRIC
        for point in metric.data.data_points
    ]
    assert points, f"{EVENT_LOOP_LAG_METRIC} was never recorded"
    assert max(p.max for p in points) >= 0.2, "a 0.3s block should surface as at least 0.2s of lag"

    # The buckets have to separate healthy from blocked, not just carry the right sum. The SDK
    # default boundaries start at 5 and are shaped for milliseconds, so recording seconds
    # against them files a 0.2ms loop and a 4s stall in the same bucket and the histogram
    # cannot answer the p99 question it exists for.
    occupied = {index for point in points for index, count in enumerate(point.bucket_counts) if count}
    assert len(occupied) > 1, (
        f"every sample landed in one bucket ({points[0].explicit_bounds}); healthy and blocked must be distinguishable"
    )
    provider.shutdown()

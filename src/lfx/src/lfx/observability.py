"""Application observability: install OTLP providers for the three signals from OTel env vars.

Application observability answers whether the service is healthy: request rates, latency,
errors, and the units of work the service performed. It is a separate concern from the LLM
tracer integrations, which describe what a flow did and carry prompt and completion text, and
the boundary between them is enforced here, on the export path.

This lives in lfx, not langflow, because lfx is the runtime that actually serves flows in
production (``lfx serve`` / ``lfx run``). The graph emits the application span, ``lfx serve``
is the HTTP surface, and both need the providers installed to export anything. langflow's
telemetry service is a thin caller of :func:`bootstrap_application_telemetry`; ``lfx serve``
calls the same function, so the two runtimes report identically to any OTLP backend.

OpenTelemetry is an optional dependency of lfx (``pip install "lfx[otel]"``). Everything here
degrades to a no-op when it is absent, so bare lfx imports this module without cost.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from lfx.log.logger import logger
from lfx.observability_fastapi import patch_otel_fastapi_route_details

if TYPE_CHECKING:
    from fastapi import FastAPI
    from opentelemetry.sdk._logs import LoggerProvider
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.trace import TracerProvider

# The tracer name Langflow's own application spans are emitted under. Deliberately not
# "langflow": the LLM tracer integrations already take a tracer under that name, and their
# spans carry flow inputs and outputs. The export filter allowlists this exact string, so a
# span emitted under any other name never reaches the operator's APM.
APPLICATION_TRACER_NAME = "langflow.observability"

# The meter name the application records its own counters and histograms on. Kept as
# "langflow" because that is the scope langflow's custom metrics already use, and the metric
# filter must allowlist it. Under bare ``lfx serve`` nothing records on this meter, so
# allowlisting it is simply harmless.
APPLICATION_METER_NAME = "langflow"

DEFAULT_SERVICE_NAME = "langflow"
SUPPORTED_OTLP_PROTOCOLS = ("grpc", "http/protobuf")

# Instrumentation scopes whose spans describe the service itself. This is an allowlist, not
# a denylist, because the LLM instrumentors ship inside the very same
# opentelemetry.instrumentation.* namespace as the application ones (openai, anthropic,
# langchain, bedrock, ... are all installed alongside fastapi and sqlalchemy). Their spans
# carry prompt and completion text, which must never reach the operator's APM, so anything
# not named here is dropped.
#
# The rule for adding to this list: only scopes the runtime itself instruments against its own
# provider. A scope is NOT safe merely because it sounds like infrastructure. The LLM vendor
# SDKs call bare Instrumentor().instrument() with no tracer_provider, which binds them to
# whatever global provider exists, i.e. ours. requests and urllib3 were on this list and had
# to be removed for exactly that reason: traceloop-sdk instruments both, so every outbound
# LLM API call produced a span here, carrying the request URL, and provider keys passed as
# query parameters travelled with it. Langflow's own uses of those two pass tracer_provider=
# explicitly, so they never route through this processor. Redis is deliberately absent for
# the same reason: traceloop-sdk instruments it and the runtime does not. sqlalchemy and httpx
# are listed ahead of the instrumentation the runtime adds for them, and carry no LLM content.
APPLICATION_INSTRUMENTATION_SCOPES = frozenset(
    {
        "opentelemetry.instrumentation.asgi",
        "opentelemetry.instrumentation.fastapi",
        "opentelemetry.instrumentation.httpx",
        "opentelemetry.instrumentation.sqlalchemy",
        APPLICATION_TRACER_NAME,
    }
)

# The same boundary for metrics. Separate from the span set because the meter the runtime
# records its own counters and histograms on is named "langflow", while its application spans
# use APPLICATION_TRACER_NAME, and because the runtime metrics below have no span equivalent.
APPLICATION_METRIC_SCOPES = APPLICATION_INSTRUMENTATION_SCOPES | {
    APPLICATION_METER_NAME,
    "opentelemetry.instrumentation.system_metrics",
}

# Runtime health for this process, deliberately not for the host.
#
# The instrumentation's default set also covers system-wide CPU, memory, disk and network.
# Those describe the machine, not the service: under Kubernetes they report the node, which
# is misleading next to a per-pod request rate, and the disk and network families multiply
# by device. An operator already has node metrics from their infrastructure agent. What they
# cannot get anywhere else is what *this* interpreter is doing, so that is what is sent.
#
# GC is included because it is the Python-specific failure mode: a service that is slow while
# CPU looks fine is usually collecting, and without this the trace shows latency with no cause.
PROCESS_METRICS_CONFIG = {
    "process.cpu.time": ["user", "system"],
    "process.cpu.utilization": ["user", "system"],
    "process.memory.usage": None,
    "process.memory.virtual": None,
    "process.thread.count": None,
    "process.open_file_descriptor.count": None,
    "process.context_switches": ["involuntary", "voluntary"],
    "cpython.gc.collections": None,
    "cpython.gc.collected_objects": None,
    "cpython.gc.uncollectable_objects": None,
}


# OpenTelemetry is optional. Resolve the SDK surface once, so the bootstrap functions can be a
# simple availability check rather than a repeated import attempt. When it is absent, every
# public entry point below returns without doing anything.
try:
    from opentelemetry import _logs, metrics, trace
    from opentelemetry.sdk._logs import LoggerProvider
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import (
        MetricExporter,
        MetricExportResult,
        MetricsData,
        PeriodicExportingMetricReader,
        ResourceMetrics,
    )
    from opentelemetry.sdk.resources import SERVICE_NAME, OTELResourceDetector, Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    _OTEL_AVAILABLE = True
except ImportError:
    _OTEL_AVAILABLE = False


if _OTEL_AVAILABLE:

    class ApplicationOnlySpanProcessor(BatchSpanProcessor):
        """Exports only spans that describe the application, dropping everything else.

        The runtime installs a global tracer provider, so any library that takes a tracer
        from it ends up exporting through this processor. That includes the LLM tracing
        integrations, whose spans carry prompts and completions. Filtering on the way out
        keeps the boundary in one place and costs the vendor integrations nothing.

        Drops are logged once per scope at debug level; they are the expected case for LLM
        instrumentation, and logging every one would be noise.

        Known consequence: an exported span whose parent was dropped arrives at the APM with a
        parent that never shows up, so the trace renders with a gap. That follows from the
        requirement of zero component spans in the APM, and it cannot be repaired here because
        a child ends before its parent, so there is no way to know at the child's on_end that
        the parent will be dropped. Scrubbing attributes instead of dropping would keep the
        tree intact, but the requirement is no component spans, not merely no content.
        """

        def __init__(self, *args, **kwargs) -> None:
            super().__init__(*args, **kwargs)
            self._dropped_scopes: set[str] = set()

        def on_end(self, span) -> None:
            scope = span.instrumentation_scope.name if span.instrumentation_scope else ""
            if scope in APPLICATION_INSTRUMENTATION_SCOPES:
                super().on_end(span)
                return
            if scope not in self._dropped_scopes:
                self._dropped_scopes.add(scope)
                logger.debug(f"Not exporting spans from {scope!r}; only application telemetry is sent to the APM.")

    class ApplicationOnlyMetricExporter(MetricExporter):
        """Pushes only the service's own metrics, dropping every other instrumentation scope.

        The metrics counterpart of ApplicationOnlySpanProcessor, and it exists for the same
        reason: the runtime installs a global meter provider, and the LLM instrumentors take
        their meters from it with a bare get_meter, so their gen_ai token and duration metrics
        would otherwise be pushed to the operator's APM alongside the service's own. Those
        belong to the LLM tracing integrations and their separate backends.

        Only the push exporter is wrapped. The local Prometheus endpoint is the flow author's
        own process and keeps seeing everything.
        """

        def __init__(self, exporter: MetricExporter) -> None:
            # Read off the wrapped exporter rather than defaulted: the temporality preference
            # is how OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=delta reaches the
            # reader, and New Relic rejects cumulative. These are the same private attributes
            # PeriodicExportingMetricReader itself reads from an exporter.
            super().__init__(
                preferred_temporality=exporter._preferred_temporality,  # noqa: SLF001
                preferred_aggregation=exporter._preferred_aggregation,  # noqa: SLF001
            )
            self._exporter = exporter
            self._dropped_scopes: set[str] = set()

        def _allowed(self, scope_name: str) -> bool:
            if scope_name in APPLICATION_METRIC_SCOPES:
                return True
            if scope_name not in self._dropped_scopes:
                self._dropped_scopes.add(scope_name)
                logger.debug(
                    f"Not exporting metrics from {scope_name!r}; only application telemetry is sent to the APM."
                )
            return False

        def export(self, metrics_data: MetricsData, timeout_millis: float = 10_000, **kwargs) -> MetricExportResult:
            resource_metrics = []
            for rm in metrics_data.resource_metrics:
                scope_metrics = [sm for sm in rm.scope_metrics if self._allowed(sm.scope.name if sm.scope else "")]
                if scope_metrics:
                    resource_metrics.append(
                        ResourceMetrics(resource=rm.resource, scope_metrics=scope_metrics, schema_url=rm.schema_url)
                    )
            # Nothing survived the filter; an empty export is a wasted round trip, not a failure.
            if not resource_metrics:
                return MetricExportResult.SUCCESS
            return self._exporter.export(MetricsData(resource_metrics=resource_metrics), timeout_millis, **kwargs)

        def force_flush(self, timeout_millis: float = 10_000) -> bool:
            return self._exporter.force_flush(timeout_millis)

        def shutdown(self, timeout_millis: float = 30_000, **kwargs) -> None:
            self._exporter.shutdown(timeout_millis, **kwargs)

    def _resource() -> Resource:
        """Build the resource, letting OTEL_SERVICE_NAME and OTEL_RESOURCE_ATTRIBUTES win.

        Resource.create() gives explicit attributes precedence over both env vars, so passing
        service.name unconditionally would make them unsettable. Ask the SDK's own detector
        whether the environment supplied one, and only fall back to our default when it did
        not. Parsing the env ourselves gets keys that merely end in service.name
        (k8s.service.name=...) and values with spaces around the = wrong.
        """
        if OTELResourceDetector().detect().attributes.get(SERVICE_NAME):
            return Resource.create()
        return Resource.create({SERVICE_NAME: DEFAULT_SERVICE_NAME})

    def _otlp_protocol(signal: str) -> str:
        """Resolve the OTLP protocol, per-signal variable first, then the generic one.

        The SDK's own auto-configuration strips whitespace and rejects unknown values; match
        that leniency so a stray space does not silently route gRPC traffic at an HTTP exporter.
        """
        protocol = (
            os.getenv(f"OTEL_EXPORTER_OTLP_{signal.upper()}_PROTOCOL")
            or os.getenv("OTEL_EXPORTER_OTLP_PROTOCOL")
            or "http/protobuf"
        ).strip()
        if protocol not in SUPPORTED_OTLP_PROTOCOLS:
            logger.warning(
                f"Unsupported OTLP protocol {protocol!r}; falling back to http/protobuf. "
                f"Supported values: {', '.join(SUPPORTED_OTLP_PROTOCOLS)}."
            )
            return "http/protobuf"
        return protocol

    def _otlp_span_exporter(protocol: str):
        """Build the OTLP span exporter; it reads endpoint, headers and timeout from the environment."""
        if protocol == "grpc":
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        else:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        return OTLPSpanExporter()

    def _prometheus_reader():
        """Build the local Prometheus pull reader, or None when the exporter is not installed.

        Prometheus is optional even within ``lfx[otel]``: a standalone ``lfx serve`` may push
        over OTLP and never expose a scrape endpoint. langflow ships the exporter and enables
        it through its own setting.
        """
        try:
            from opentelemetry.exporter.prometheus import PrometheusMetricReader
        except ImportError:
            logger.warning("Prometheus metrics requested but opentelemetry-exporter-prometheus is not installed.")
            return None
        return PrometheusMetricReader()

    def _otlp_metric_reader() -> PeriodicExportingMetricReader | None:
        """Build the OTLP push reader when the standard OTel env vars opt in.

        The exporter and the reader take no arguments on purpose: endpoint, headers, timeout,
        compression, export interval and OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE
        (New Relic requires delta) all come from the environment, and passing any of them here
        would make the corresponding variable unsettable.

        The final flush on exit needs no wiring: MeterProvider registers its own atexit handler
        (shutdown_on_exit defaults to True), which shuts the reader down and drains it.
        """
        endpoint = os.getenv("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT") or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
        if not endpoint:
            return None

        # The operator's documented way to turn metrics off while leaving a shared endpoint set.
        if os.getenv("OTEL_METRICS_EXPORTER", "otlp").strip().lower() == "none":
            return None

        protocol = _otlp_protocol("metrics")
        try:
            if protocol == "grpc":
                from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
            else:
                from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
            reader = PeriodicExportingMetricReader(ApplicationOnlyMetricExporter(OTLPMetricExporter()))
        except Exception:  # noqa: BLE001
            logger.warning("Could not configure the OTLP metric exporter; metrics will not be pushed.")
            return None

        # Without this, a protocol/port mismatch is indistinguishable from never having booted.
        logger.info(f"OTLP metric export enabled (protocol={protocol}, endpoint={endpoint}).")
        return reader

    def _install_meter_provider(*, prometheus_enabled: bool) -> MeterProvider:
        """Install (or reuse) the meter provider carrying the Prometheus and OTLP readers."""
        existing_provider = metrics.get_meter_provider()
        # Reuse a concrete SDK provider installed by another integration. The default API proxy
        # also returns meters, but it has no readers and must be replaced so the readers below
        # can collect.
        if isinstance(existing_provider, MeterProvider):
            return existing_provider

        metric_readers = []
        if prometheus_enabled:
            reader = _prometheus_reader()
            if reader is not None:
                metric_readers.append(reader)
        # Prometheus is a pull endpoint, so it cannot cover a process that exits between
        # scrapes. Both readers sit on the one provider.
        otlp_reader = _otlp_metric_reader()
        if otlp_reader is not None:
            metric_readers.append(otlp_reader)

        provider = MeterProvider(resource=_resource(), metric_readers=metric_readers)
        metrics.set_meter_provider(provider)
        return provider

    def _instrument_process_metrics(meter_provider: MeterProvider) -> None:
        """Report this process's CPU, memory, threads, file descriptors and GC.

        Bound to our meter provider explicitly rather than the global one, so these land on
        the same readers as everything else even if another integration installs a provider
        later. Failure is non-fatal: missing runtime metrics degrade the dashboard, they do
        not justify refusing to boot.
        """
        try:
            from opentelemetry.instrumentation.system_metrics import SystemMetricsInstrumentor

            instrumentor = SystemMetricsInstrumentor(config=PROCESS_METRICS_CONFIG)
            # The instrumentor is a singleton and raises if instrumented twice, which happens
            # in-process across app restarts and in tests.
            if not instrumentor.is_instrumented_by_opentelemetry:
                instrumentor.instrument(meter_provider=meter_provider)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Could not start process metrics; runtime health will be missing. {exc}")

    def _configure_tracer_provider_from_environment() -> TracerProvider | None:
        """Install an OTLP tracer provider when the standard OTel env vars opt in.

        Nothing sets a tracer provider otherwise, so spans go nowhere. If application code
        or opentelemetry-instrument already installed one, leave it alone.
        """
        endpoint = os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT") or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
        if not endpoint:
            return None

        # The operator's documented way to turn traces off while leaving a shared endpoint set.
        if os.getenv("OTEL_TRACES_EXPORTER", "otlp").strip().lower() == "none":
            return None

        if trace.get_tracer_provider().__class__.__name__ != "ProxyTracerProvider":
            # Someone else owns tracing (opentelemetry-instrument, the OTel operator, or app
            # code). Installing over it would break them, but it also means our export filter
            # is not in the path, so nothing stops the LLM tracer integrations from sending
            # prompt content to that provider's exporter. Say so rather than implying a
            # boundary we are not enforcing.
            logger.warning(
                "A tracer provider is already installed, so OTLP export is not being configured. "
                "LLM tracing integrations may export prompt and completion content through it."
            )
            return None

        protocol = _otlp_protocol("traces")
        try:
            tracer_provider = TracerProvider(resource=_resource())
            tracer_provider.add_span_processor(ApplicationOnlySpanProcessor(_otlp_span_exporter(protocol)))
        except Exception:  # noqa: BLE001
            logger.warning("Could not configure the OTLP tracer provider; traces will not be exported.")
            return None

        trace.set_tracer_provider(tracer_provider)
        # Without this, a protocol/port mismatch is indistinguishable from never having booted.
        logger.info(f"OTLP trace export enabled (protocol={protocol}, endpoint={endpoint}).")
        return tracer_provider

    def _configure_logger_provider_from_environment() -> LoggerProvider | None:
        """Install an OTLP logger provider when the standard OTel env vars opt in.

        This is the third signal, and the one that makes a trace actionable: the operator
        pivots from a failed request to the log lines emitted inside it. Correlation is
        automatic because the SDK stamps the active span's trace_id onto every record, and
        each flow execution already runs inside a span.
        """
        endpoint = os.getenv("OTEL_EXPORTER_OTLP_LOGS_ENDPOINT") or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
        if not endpoint:
            return None
        if os.getenv("OTEL_LOGS_EXPORTER", "otlp").strip().lower() == "none":
            return None
        if isinstance(_logs.get_logger_provider(), LoggerProvider):
            logger.warning("A logger provider is already installed; not replacing it.")
            return None

        protocol = _otlp_protocol("logs")
        try:
            if protocol == "grpc":
                from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
            else:
                from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter

            provider = LoggerProvider(resource=_resource())
            provider.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter()))
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Could not configure the OTLP log exporter; logs will not be shipped. {exc}")
            return None

        _logs.set_logger_provider(provider)
        logger.info(f"OTLP log export enabled (protocol={protocol}, endpoint={endpoint}).")
        return provider


@dataclass
class ApplicationTelemetry:
    """The providers a call to :func:`bootstrap_application_telemetry` installed.

    Each is None when the corresponding signal was not configured (no endpoint, disabled, or
    OpenTelemetry not installed). Callers that own the process lifetime can keep the handles
    to shut down explicitly; most do not need to, because MeterProvider registers its own
    atexit flush.
    """

    meter_provider: MeterProvider | None = None
    tracer_provider: TracerProvider | None = None
    logger_provider: LoggerProvider | None = None


def bootstrap_application_telemetry(*, prometheus_enabled: bool = False) -> ApplicationTelemetry:
    """Install OTLP providers for traces, metrics and logs from the standard OTel env vars.

    This is the single entry point both runtimes call: langflow's telemetry service and
    ``lfx serve``. It is a no-op returning empty handles when OpenTelemetry is not installed,
    and reuses an already-installed provider rather than replacing it, so calling it once per
    process is safe.

    ``prometheus_enabled`` adds the local Prometheus pull reader alongside the OTLP push
    reader. It defaults off: a standalone ``lfx serve`` typically pushes over OTLP and exposes
    no scrape endpoint, while langflow passes its own setting through.
    """
    if not _OTEL_AVAILABLE:
        return ApplicationTelemetry()

    meter_provider = _install_meter_provider(prometheus_enabled=prometheus_enabled)
    _instrument_process_metrics(meter_provider)
    tracer_provider = _configure_tracer_provider_from_environment()
    logger_provider = _configure_logger_provider_from_environment()
    return ApplicationTelemetry(
        meter_provider=meter_provider,
        tracer_provider=tracer_provider,
        logger_provider=logger_provider,
    )


def instrument_fastapi_app(app: FastAPI) -> None:
    """Instrument an ASGI app for HTTP server telemetry under the stable conventions.

    Both runtimes serve over FastAPI, so both call this on their app: langflow on its main
    app, ``lfx serve`` on the multi-flow app. No-op when the FastAPI instrumentation is not
    installed.

    Sets the stable HTTP semantic conventions (http.route, http.request.method,
    http.response.status_code) rather than the pre-1.0 names, because APMs key their HTTP
    dashboards and service maps off the stable ones. It has to run before instrument_app: the
    opt-in is read once, on first instrumentation, and cached for the life of the process.
    setdefault leaves "http/dup" available to an operator migrating.
    """
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    except ImportError:
        return

    os.environ.setdefault("OTEL_SEMCONV_STABILITY_OPT_IN", "http")
    # FastAPI >=0.137 lazy include_router puts _IncludedRouter wrappers (no .path) in
    # app.routes, which crashes OTel's span route extraction on partial matches (e.g. CORS
    # preflight). Patch the helper before instrumenting.
    patch_otel_fastapi_route_details()
    FastAPIInstrumentor.instrument_app(app)

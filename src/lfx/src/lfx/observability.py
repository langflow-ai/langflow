"""Application observability: install OTLP providers for the three signals from OTel env vars.

Application observability answers whether the service is healthy: request rates, latency,
errors, and the units of work the service performed. It is a separate concern from the LLM
tracer integrations, which describe what a flow did and carry prompt and completion text.

The boundary between them is drawn per signal, all three deny by default on the way out. Spans go
through ``ApplicationOnlySpanProcessor`` and metrics through ``ApplicationOnlyMetricExporter``,
both below, each allowlisting an instrumentation scope. Logs are filtered in ``lfx.log.logger``,
where a record is assembled, and on a declared opt-in rather than a scope name, because a log
record's scope is derived from the calling module and so is not something a call site can be
trusted to have chosen.

Worth knowing when reading the claim we make about this: the filter covers what this process
exports over OTLP, and nothing else. The console and the rotating log file still contain every
message in full, so shipping those to the same backend goes around it.

This lives in lfx, not langflow, because lfx is the runtime that actually serves flows in
production (``lfx serve`` / ``lfx run``). The graph emits the application span, ``lfx serve``
is the HTTP surface, and both need the providers installed to export anything. langflow's
telemetry service is a thin caller of :func:`bootstrap_application_telemetry`; ``lfx serve``
calls the same function, so the two runtimes report identically to any OTLP backend.

OpenTelemetry is an optional dependency of lfx (``pip install "lfx[otel]"``). Everything here
degrades to a no-op when it is absent, so bare lfx imports this module without cost.
"""

from __future__ import annotations

import asyncio
import builtins
import contextlib
import contextvars
import importlib
import os
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import urlsplit, urlunsplit

from lfx.log.logger import logger, operator_logger, otel_log_bodies_exported
from lfx.observability_fastapi import patch_otel_fastapi_route_details

_BASE_EXCEPTION_GROUP_TYPE = getattr(builtins, "BaseExceptionGroup", None)
if _BASE_EXCEPTION_GROUP_TYPE is None:
    # The backport is present with the supported Python 3.10 dependency set, but
    # observability must remain importable in a deliberately minimal bare-lfx install.
    with contextlib.suppress(ImportError):
        _BASE_EXCEPTION_GROUP_TYPE = importlib.import_module("exceptiongroup").BaseExceptionGroup

if TYPE_CHECKING:
    from collections.abc import Iterator

    from fastapi import FastAPI
    from opentelemetry.sdk._logs import LoggerProvider
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.trace import Span

# The tracer name Langflow's own application spans are emitted under. Deliberately not
# "langflow": the LLM tracer integrations already take a tracer under that name, and their
# spans carry flow inputs and outputs. The export filter allowlists this exact string, so a
# span emitted under any other name never reaches the operator's APM.
APPLICATION_TRACER_NAME = "langflow.observability"

# The meter name the application records its own counters and histograms on. Kept as
# "langflow" because that is the scope langflow's custom metrics already use, and the metric
# filter must allowlist it. Under bare ``lfx serve`` the only thing recording here is the
# event-loop lag sampler below; langflow's own counters and gauges are additional.
APPLICATION_METER_NAME = "langflow"

DEFAULT_SERVICE_NAME = "langflow"

# The surface a flow run arrived through, recorded as the flow span's ``protocol`` attribute so
# an operator can tell a playground click from a webhook delivery from an MCP tool call.
#
# Ambient rather than a parameter because the graph is several layers below the surface that
# knows the answer, and two of those layers hand the run to a fresh asyncio task. Task creation
# copies the context, so setting this at the entry point carries it into the run without
# threading an argument through every intermediate signature. It also means a path nobody wired
# reports no protocol at all rather than inheriting a wrong one from its caller.
_current_protocol: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "lfx_execution_protocol",
    default=None,
)


# The client a run says it came from, recorded as the span's ``client`` attribute. Distinct from
# ``protocol`` on purpose: protocol is how the request arrived and is derived server-side from the
# route, while this is who the caller claims to be. Conflating them is a mistake worth naming,
# because the playground calls the same public API any user would, so the route cannot identify it.
#
# Self-reported and therefore spoofable. That is fine for telemetry and must never become an
# authorization signal. The vocabulary is closed so a caller cannot mint attribute values at will;
# anything unrecognised is dropped rather than recorded, on the same principle as protocol, where a
# missing attribute is an honest "nobody said" and a guessed one is a lie.
KNOWN_EXECUTION_CLIENTS = frozenset({"playground", "sdk", "cli"})

# Follows the X-LANGFLOW-* convention already used for request-scoped global variables.
EXECUTION_CLIENT_HEADER = "x-langflow-client"

_current_client: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "lfx_execution_client",
    default=None,
)


def get_execution_client() -> str | None:
    """Return the client the current run says it came from, or None if it did not say."""
    return _current_client.get()


@contextlib.contextmanager
def execution_client(client: str | None) -> Iterator[None]:
    """Bind *client* for the current context, ignoring anything outside the known vocabulary."""
    if client not in KNOWN_EXECUTION_CLIENTS:
        yield
        return
    token = _current_client.set(client)
    try:
        yield
    finally:
        _current_client.reset(token)


def get_execution_protocol() -> str | None:
    """Return the surface the current flow run arrived through, or None outside a served run."""
    return _current_protocol.get()


@contextlib.contextmanager
def execution_protocol(protocol: str) -> Iterator[None]:
    """Bind *protocol* as the surface for flow runs started in this context, outermost wins.

    An already-bound protocol is left alone, because several surfaces share one driver
    underneath: voice and the playground both reach the graph through the same build path, and
    a flow-as-tool child run reaches it through whichever surface called the parent. In every
    such pair the outer binding is the one that names how the request actually arrived, so the
    inner generic driver must not overwrite it.

    Reset on exit so a worker that serves many requests on one task cannot leak one request's
    protocol into the next. A run handed to ``asyncio.create_task`` inside the block keeps the
    value regardless, because the task copies the context at creation.

    Entry points bind with this. The one exception is a callee that is itself an async
    generator: an async generator body runs in the context of whoever calls ``__anext__``, so a
    scope wrapped around it from outside would set and reset across its suspension points. Those
    take a plain ``protocol`` argument and bind it inside, on the coroutine that does the work
    (see ``_stream_event_frames``).
    """
    if _current_protocol.get() is not None:
        yield
        return
    token = _current_protocol.set(protocol)
    try:
        yield
    finally:
        _current_protocol.reset(token)


# Event-loop scheduling delay. Sampled rather than instrumented: there is no hook that
# reports "the loop was blocked", so the only way to see it is to ask for a known sleep and
# measure how late the answer comes back.
EVENT_LOOP_LAG_METRIC = "langflow_event_loop_lag_seconds"
EVENT_LOOP_LAG_INTERVAL_SECONDS = 0.25

# Explicit buckets, because the SDK default boundaries start (0, 5, 10, 25, ...) and are
# shaped for milliseconds. Recording seconds against them puts a healthy 0.2ms loop and a
# catastrophic 4s stall in the same bucket, which makes the histogram unable to answer the
# one question it exists for. These span "healthy" (sub-millisecond) to "the loop is gone".
EVENT_LOOP_LAG_BUCKETS_SECONDS = (0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
SUPPORTED_OTLP_PROTOCOLS = ("grpc", "http/protobuf")

# The endpoint vars that mean "an operator wants to export". Any one of these being set is the
# signal that observability was intended, used to turn an otel-not-installed situation from a
# silent no-op into a loud "you meant to export, install the extra" warning.
_OTLP_ENDPOINT_VARS = (
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
    "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT",
    "OTEL_EXPORTER_OTLP_LOGS_ENDPOINT",
)

# Instrumentation scopes whose spans describe the service itself. This is an allowlist, not
# a denylist, because the LLM instrumentors ship inside the very same
# opentelemetry.instrumentation.* namespace as the application ones (openai, anthropic,
# langchain, bedrock, ... are all installed alongside fastapi and sqlalchemy). Their spans
# carry prompt and completion text, which must never reach the operator's APM, so anything
# not named here is dropped.
#
# The rule for adding to this list: only scopes the runtime instruments *right now*, against
# its own provider. A scope is NOT safe merely because it sounds like infrastructure, and it is
# NOT safe to list speculatively "for when we instrument it". The LLM vendor SDKs call bare
# Instrumentor().instrument() with no tracer_provider, which binds them to whatever global
# provider exists, i.e. ours. requests and urllib3 were on this list and had to be removed for
# exactly that reason: traceloop-sdk instruments both, so every outbound LLM API call produced
# a span here, carrying the request URL, and provider keys passed as query parameters travelled
# with it. httpx is the same trap and is the transport the openai and anthropic SDKs ride on,
# so it is deliberately absent until the runtime instruments it with an explicit
# tracer_provider=. sqlalchemy and redis are absent for the same reason: nothing here
# instruments them today, so listing them would only open a hole for a global instrumentor.
# Only asgi and fastapi (installed by instrument_fastapi_app) and APPLICATION_TRACER_NAME (the
# flow span) are emitted against our provider, so only they are listed. Re-add a scope the same
# commit that wires its instrumentor with tracer_provider=, never before.
APPLICATION_INSTRUMENTATION_SCOPES = frozenset(
    {
        "opentelemetry.instrumentation.asgi",
        "opentelemetry.instrumentation.fastapi",
        # DB spans. Admitted after checking what they actually carry: db.statement keeps bound
        # parameters as placeholders ("INSERT INTO messagetable (text) VALUES (?)"), so chat
        # message text stays in the database and out of the APM. Verified by probe, because
        # "it probably does not log values" is how the httpx hole got opened the first time.
        #
        # The outbound HTTP scopes (httpx, requests, urllib3) remain deliberately absent. The
        # LLM vendor SDKs instrument them globally against whatever provider is global (ours),
        # so admitting them would put one span per outbound LLM call in the operator's APM.
        # Outbound provider health is delivered as leak-safe metrics instead.
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


# Environment resolution shared with the doctor (``lfx observability doctor``). These are plain
# os.getenv and deliberately sit outside the otel-guarded block below, so the self-test can
# import them at module scope and resolve endpoints exactly the way the bootstrap does. Keeping
# one definition is the point: a doctor that resolved endpoints its own way could report a
# healthy pipeline the runtime never exports to.


def otlp_endpoint(signal: str) -> str | None:
    """Resolve a signal's endpoint: the per-signal variable first, then the generic one."""
    return os.getenv(f"OTEL_EXPORTER_OTLP_{signal.upper()}_ENDPOINT") or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")


def otlp_exporter_disabled(signal: str) -> bool:
    """Whether the operator turned this signal off while leaving a shared endpoint set."""
    return os.getenv(f"OTEL_{signal.upper()}_EXPORTER", "otlp").strip().lower() == "none"


# C0 controls plus DEL. None can appear in a URL, and urlsplit strips a subset of them silently.
_CONTROL_CHARACTERS = frozenset(chr(code) for code in [*range(0x20), 0x7F])


def safe_endpoint(endpoint: str) -> str:
    """An OTLP endpoint with its credentials removed, for printing.

    The endpoint is operator-supplied and routinely carries a token, either as userinfo in the
    authority or as a query parameter; both are how vendors document their collectors. The
    startup line that reports the endpoint is now on the one log scope whose bodies are exported
    verbatim, so without this, closing the log body boundary would open a credential leak through
    the line announcing it.

    Userinfo and query string go; scheme, host, port and path stay, because a wrong port is the
    thing this line exists to make visible. Unparseable input degrades to a fixed marker rather
    than raising, since this only ever runs to build a log message.

    Control characters are rejected outright rather than parsed. ``urlsplit`` silently strips
    tab, carriage return and newline per WHATWG, which quietly rejoins whatever followed one of
    them into the path, so an endpoint with an embedded newline comes back as a single line with
    the injected text appended to the path, and that line is written verbatim to the one log
    scope that is exported. A URL cannot legally contain them, so their presence means this is
    not a URL.
    """
    if _CONTROL_CHARACTERS.intersection(endpoint):
        return "<unparseable endpoint>"
    try:
        parts = urlsplit(endpoint)
        _ = parts.port  # Validates the authority; a bad port raises here rather than later.
    except ValueError:
        return "<unparseable endpoint>"
    # An endpoint with no authority is not an endpoint, and the failure mode is the one this
    # function exists to prevent: ``urlsplit`` treats ``https:sekrit`` as an opaque value and
    # parks the whole of it in ``path``, so a typo that drops the slashes would have printed the
    # secret verbatim on the one log scope that is exported. Same for a bare word with no scheme.
    if not parts.netloc:
        return "<unparseable endpoint>"
    netloc = parts.netloc.rsplit("@", maxsplit=1)[-1]
    return urlunsplit((parts.scheme, netloc, parts.path, "", ""))


def otlp_exporter_class(signal: str, protocol: str):
    """The OTLP exporter class for a signal and protocol.

    Returns the class rather than an instance because the callers differ: the bootstrap wants a
    default-constructed exporter reading the environment, while the doctor passes an explicit
    timeout. Spelled out once here so a signal/protocol pairing cannot be wrong in one place and
    right in another.
    """
    if signal == "traces":
        if protocol == "grpc":
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter as ExporterClass
        else:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter as ExporterClass
    elif signal == "metrics":
        if protocol == "grpc":
            from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter as ExporterClass
        else:
            from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter as ExporterClass
    elif protocol == "grpc":
        from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter as ExporterClass
    else:
        from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter as ExporterClass
    return ExporterClass


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
                _redact_url_attributes(span)
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
        endpoint = otlp_endpoint("metrics")
        if not endpoint:
            return None

        # The operator's documented way to turn metrics off while leaving a shared endpoint set.
        if otlp_exporter_disabled("metrics"):
            return None

        protocol = _otlp_protocol("metrics")
        try:
            exporter = otlp_exporter_class("metrics", protocol)()
            reader = PeriodicExportingMetricReader(ApplicationOnlyMetricExporter(exporter))
        except Exception:  # noqa: BLE001
            logger.warning("Could not configure the OTLP metric exporter; metrics will not be pushed.")
            return None

        # Without this, a protocol/port mismatch is indistinguishable from never having booted.
        operator_logger().info(f"OTLP metric export enabled (protocol={protocol}, endpoint={safe_endpoint(endpoint)}).")
        return reader

    def _install_meter_provider(*, prometheus_enabled: bool) -> tuple[MeterProvider | None, bool]:
        """Install (or reuse) the meter provider carrying the Prometheus and OTLP readers.

        Returns ``(provider, owned)``. ``owned`` is True only when this call constructed the
        provider, so the shutdown path never tears down a provider that belongs to someone else.
        """
        existing_provider = metrics.get_meter_provider()
        # Reuse a concrete SDK provider installed by another integration. The default API proxy
        # also returns meters, but it has no readers and must be replaced so the readers below
        # can collect. Adopted, not owned: it is not ours to shut down.
        if isinstance(existing_provider, MeterProvider):
            return existing_provider, False

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

        if not metric_readers:
            # Nothing to scrape or export. Installing a reader-less provider would still replace
            # the API proxy globally (set_meter_provider is first-write-wins), silently blocking a
            # provider a later integration or the embedding app installs, while never emitting
            # anything. The traces and logs paths decline the same way when nothing is configured.
            return None, False

        provider = MeterProvider(resource=_resource(), metric_readers=metric_readers)
        metrics.set_meter_provider(provider)
        return provider, True

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
        endpoint = otlp_endpoint("traces")
        if not endpoint:
            return None

        # The operator's documented way to turn traces off while leaving a shared endpoint set.
        if otlp_exporter_disabled("traces"):
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
            exporter = otlp_exporter_class("traces", protocol)()
            tracer_provider.add_span_processor(ApplicationOnlySpanProcessor(exporter))
        except Exception:  # noqa: BLE001
            logger.warning("Could not configure the OTLP tracer provider; traces will not be exported.")
            return None

        trace.set_tracer_provider(tracer_provider)
        # Without this, a protocol/port mismatch is indistinguishable from never having booted.
        operator_logger().info(f"OTLP trace export enabled (protocol={protocol}, endpoint={safe_endpoint(endpoint)}).")
        return tracer_provider

    def _configure_logger_provider_from_environment() -> LoggerProvider | None:
        """Install an OTLP logger provider when the standard OTel env vars opt in.

        This is the third signal, and the one that makes a trace actionable: the operator
        pivots from a failed request to the log lines emitted inside it. Correlation is
        automatic because the SDK stamps the active span's trace_id onto every record, and
        each flow execution already runs inside a span.
        """
        endpoint = otlp_endpoint("logs")
        if not endpoint:
            return None
        if otlp_exporter_disabled("logs"):
            return None
        if isinstance(_logs.get_logger_provider(), LoggerProvider):
            logger.warning("A logger provider is already installed; not replacing it.")
            return None

        protocol = _otlp_protocol("logs")
        try:
            provider = LoggerProvider(resource=_resource())
            exporter = otlp_exporter_class("logs", protocol)()
            provider.add_log_record_processor(BatchLogRecordProcessor(exporter))
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Could not configure the OTLP log exporter; logs will not be shipped. {exc}")
            return None

        _logs.set_logger_provider(provider)
        _announce_log_export(protocol, endpoint)
        return provider

    def _announce_log_export(protocol: str, endpoint: str) -> None:
        """State the log boundary in the operator's own log stream, at boot.

        Documentation does not reach the person writing the Helm values, and this is the signal
        with the residual exposure worth knowing about: the body filter covers what Langflow
        exports over OTLP, and nothing else. Container stdout and the rotating log file still
        carry every message in full, so a sidecar log shipper reaches the same backend by a route
        this process never sees. That is a deployment choice, and it is only a deliberate one if
        the operator has been told.

        WARNING rather than INFO when the logs endpoint was inherited from the shared
        ``OTEL_EXPORTER_OTLP_ENDPOINT``, because then shipping logs was a side effect of
        configuring traces rather than a decision. Setting the per-signal variable says the
        operator meant it, and earns the quieter level.
        """
        inherited = not os.getenv("OTEL_EXPORTER_OTLP_LOGS_ENDPOINT")
        bodies_exported = otel_log_bodies_exported()
        boundary = (
            "Message bodies ARE exported (LANGFLOW_OTEL_LOG_BODIES=all); they carry model "
            "completions, chat history and provider error text."
            if bodies_exported
            else "Message bodies are withheld unless a call site opts in; records keep severity, "
            "scope, callsite, error.type and trace correlation."
        )
        message = (
            f"OTLP log export enabled (protocol={protocol}, endpoint={safe_endpoint(endpoint)}). "
            f"{boundary} This filter covers OTLP only: container stdout and the local log file "
            f"still contain full messages, so shipping those to the same backend bypasses it. "
            f"Set OTEL_LOGS_EXPORTER=none to export traces and metrics without logs."
        )
        if inherited:
            operator_logger().warning(
                f"{message} Logs were enabled by the shared OTEL_EXPORTER_OTLP_ENDPOINT; set "
                f"OTEL_EXPORTER_OTLP_LOGS_ENDPOINT to make that explicit."
            )
        else:
            operator_logger().info(message)


@dataclass
class ApplicationTelemetry:
    """The providers a call to :func:`bootstrap_application_telemetry` installed.

    Each is None when the corresponding signal was not configured (no endpoint, disabled, or
    OpenTelemetry not installed). Callers that own the process lifetime should keep the handles
    and call :meth:`shutdown` on exit: the atexit flush the SDK registers does not run under
    uvicorn or gunicorn (both die by signal), so without an explicit shutdown the last buffered
    batch of spans, metrics and logs is dropped on every restart and pod eviction.
    """

    meter_provider: MeterProvider | None = None
    tracer_provider: TracerProvider | None = None
    logger_provider: LoggerProvider | None = None
    # True only when the bootstrap constructed the meter provider. A provider adopted from
    # another integration is theirs to shut down. The tracer and logger providers need no such
    # flag: their paths decline to install over an existing provider and return None, so a
    # non-None handle here is always one we installed.
    owns_meter_provider: bool = False

    def shutdown(self) -> None:
        """Flush and shut down the providers this bootstrap installed. A no-op when none were.

        Meter first: only ``MeterProvider.shutdown`` unregisters its atexit flush, and skipping
        it lets the interpreter shut the readers down a second time (Prometheus raises on the
        double unregister). The meter provider is shut down only when we own it, so an adopted
        provider's pipeline (which may outlive this process in an embedded host) is left intact.
        """
        if self.meter_provider is not None and self.owns_meter_provider:
            self.meter_provider.shutdown()
        if self.tracer_provider is not None:
            self.tracer_provider.shutdown()
        if self.logger_provider is not None:
            self.logger_provider.shutdown()


# URL attributes an HTTP instrumentor may set. Every one of them can carry a full URL, and a
# full URL can carry a credential: providers put API keys in the query string (Gemini's
# ?key=, several others), and a URL may also carry userinfo before the host.
_URL_SPAN_ATTRIBUTES = ("http.url", "url.full", "http.target", "url.query")


def _redact_url_attributes(span) -> None:
    """Strip query strings and userinfo from a span's URL attributes, in place.

    A live leak, not a hypothetical, and on a scope that is already allowlisted: the FastAPI
    server span records ``url.query`` verbatim, and ``lfx serve`` accepts its API key as a
    query parameter (``APIKeyQuery``). A probe against the real instrumented app exports
    ``url.query = "x-api-key=<the key>"``, so any deployment whose callers pass the key that
    way has been sending it to the operator's APM.

    Done at the export boundary rather than through an instrumentor hook because this is the
    same place that already decides what leaves: one chokepoint, and it covers instrumentors
    the runtime does not install itself.

    Scheme, host, port, path and every non-URL attribute survive, so "POST api.openai.com
    /v1/chat/completions took 3s" still reads exactly as an operator needs it to.
    """
    attributes = span.attributes
    if not attributes or not any(key in attributes for key in _URL_SPAN_ATTRIBUTES):
        return

    original_attributes = span._attributes  # noqa: SLF001
    redacted = dict(attributes)

    for key in _URL_SPAN_ATTRIBUTES:
        if key not in attributes:
            continue
        if key == "url.query":
            # The whole point of this attribute is the query string, so there is nothing to keep.
            redacted[key] = ""
        else:
            value = attributes[key]
            if not isinstance(value, str) or (
                original_attributes.max_value_len is not None and len(value) >= original_attributes.max_value_len
            ):
                # A sequence is not a valid semantic URL value. A value at the SDK's length cap
                # may have lost its query or userinfo delimiter, so neither can be redacted safely.
                redacted[key] = ""
                continue
            try:
                parts = urlsplit(value)
                # Accessing port validates the authority. Keep using the raw netloc below so
                # bracketed IPv6 and port zero retain their exact valid representation.
                _ = parts.port
            except ValueError:
                # Telemetry must never break request handling. A malformed authority is not useful
                # operational data, so fail closed rather than exporting it or raising from Span.end().
                redacted[key] = ""
            else:
                # Strip userinfo from the raw authority instead of rebuilding it from hostname/port:
                # the raw form preserves IPv6 brackets and port zero.
                netloc = parts.netloc.rsplit("@", maxsplit=1)[-1]
                missing_authority = not netloc and (
                    key in ("http.url", "url.full") or parts.scheme.lower() in ("http", "https", "ws", "wss")
                )
                if missing_authority:
                    # Absolute URL attributes and hierarchical HTTP-style values require an
                    # authority. Otherwise credential-looking bytes may be hiding in the path.
                    redacted[key] = ""
                else:
                    redacted[key] = urlunsplit((parts.scheme, netloc, parts.path, "", ""))

    # Imported here, not at module scope: opentelemetry is an optional lfx extra and this
    # module must stay importable without it.
    from opentelemetry.attributes import BoundedAttributes

    # Span.end() freezes the SDK's BoundedAttributes before processors run, and ReadableSpan
    # exposes no public setter. Rebuild the immutable mapping with its original limits and
    # carry the prior drop count forward so exporters receive the same span metadata.
    redacted_attributes = BoundedAttributes(
        maxlen=original_attributes.maxlen,
        attributes=redacted,
        max_value_len=original_attributes.max_value_len,
    )
    redacted_attributes.dropped = original_attributes.dropped
    span._attributes = redacted_attributes  # noqa: SLF001


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
        # Silence here is a real DX trap: an operator sets the endpoint, restarts, sees nothing
        # in their APM, and has no way to know the reason is a missing dependency rather than a
        # wrong endpoint. Only warn when they clearly intended to export.
        if any(os.getenv(var) for var in _OTLP_ENDPOINT_VARS):
            logger.warning(
                "An OTLP endpoint is configured but OpenTelemetry is not installed, so no "
                "telemetry will be exported. Install it with: pip install 'lfx[otel]' (the full "
                "langflow distribution already includes it)."
            )
        return ApplicationTelemetry()

    meter_provider, owns_meter_provider = _install_meter_provider(prometheus_enabled=prometheus_enabled)
    if meter_provider is not None:
        _instrument_process_metrics(meter_provider)
    tracer_provider = _configure_tracer_provider_from_environment()
    logger_provider = _configure_logger_provider_from_environment()
    return ApplicationTelemetry(
        meter_provider=meter_provider,
        owns_meter_provider=owns_meter_provider,
        tracer_provider=tracer_provider,
        logger_provider=logger_provider,
    )


def instrument_database(engine: object) -> None:
    """Instrument a SQLAlchemy engine, so a slow request can be attributed to its queries.

    Takes the engine rather than instrumenting globally. Langflow's engine is an AsyncEngine and
    the instrumentor patches the sync engine underneath it; a global ``instrument()`` with no
    engine attaches to pool events only, which produces a connect span per checkout and no query
    spans at all. Verified against a live backend: 13 connect spans and zero db.statement for one
    API request. That is worse than nothing, because it looks like DB visibility.

    Deliberately does not instrument httpx or requests. Those are the transports the LLM vendor
    SDKs ride on, and instrumenting them globally would put one span per outbound provider call
    into the operator's APM.

    Optional and failure-tolerant: a missing package or a double-instrument call must not take
    the app down, because none of this is worth a failed boot.
    """
    _instrument_sqlalchemy(engine)


def _instrument_sqlalchemy(engine: object) -> None:
    try:
        from opentelemetry import trace
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    except ImportError:
        return
    try:
        SQLAlchemyInstrumentor().instrument(
            # An AsyncEngine exposes the sync one the instrumentor actually patches.
            engine=getattr(engine, "sync_engine", engine),
            tracer_provider=trace.get_tracer_provider(),
        )
    except Exception:  # noqa: BLE001 - see above
        logger.debug("sqlalchemy instrumentation unavailable; DB spans will be missing", exc_info=True)


class OutboundCallScope:
    """Handle for a caller that learns the outcome after the call returns.

    A protocol that reports failure in its return value rather than by raising leaves the span
    with nothing to see. MCP is one: a failed tool call comes back as a ``CallToolResult`` with
    ``isError`` set, so without this the span closes OK and the operator's error rate on
    outbound calls is zero no matter how many tools are failing.

    Takes an error type, never a message or a result: the failure text a server returns embeds
    the arguments it was called with.
    """

    __slots__ = ("error_type", "span")

    def __init__(self, span: Span | None = None) -> None:
        self.error_type: str | None = None
        self.span = span

    def record_error(self, error_type: str) -> None:
        # First failure wins, so a later one cannot overwrite the one that caused the retry.
        if self.error_type is None:
            self.error_type = error_type

    def set_attribute(self, key: str, value: str) -> None:
        """Record an identifier the caller only learns mid-call.

        A2A only learns which agent it reached after resolving the remote card, which is itself
        part of the call the span covers. Same boundary as the opening attributes: identifiers
        only, never a message, an argument or a result.
        """
        if self.span is not None:
            self.span.set_attribute(key, value)


def _root_error_type(exc: BaseException) -> str:
    """Name the exception that actually failed, not the one the retry loop wrapped it in.

    Both MCP retry loops re-raise as ``ValueError(f"Failed to run tool ...")`` with ``from e``,
    so without walking the chain every timeout, dropped connection and closed resource records
    as ``ValueError`` and the attribute tells an operator nothing. Transport task groups can
    also wrap one actionable failure in an exception group; a group is unwrapped only when it
    has one member, because a multi-error group has no single root type. Only the type is read;
    the message stays unrecorded either way.
    """
    root = exc
    seen = {id(root)}
    while True:
        # asyncio implements wait_for timeouts by cancelling the inner task, so TimeoutError
        # explicitly chains a CancelledError. The timeout is the actionable failure; the inner
        # cancellation is an implementation detail. A real outer cancellation still arrives as
        # CancelledError directly and is reported as such.
        if isinstance(root, (asyncio.TimeoutError, TimeoutError)):
            break
        next_error = root.__cause__
        if (
            next_error is None
            and _BASE_EXCEPTION_GROUP_TYPE is not None
            and isinstance(root, _BASE_EXCEPTION_GROUP_TYPE)
        ):
            grouped = root.exceptions
            if isinstance(grouped, tuple) and len(grouped) == 1 and isinstance(grouped[0], BaseException):
                next_error = grouped[0]
        if next_error is None or id(next_error) in seen:
            break
        root = next_error
        seen.add(id(root))
    return type(root).__name__


@contextlib.contextmanager
def outbound_call_span(name: str, attributes: dict[str, str]) -> Iterator[OutboundCallScope]:
    """One span for an outbound call the runtime makes itself, for the operator's APM.

    Emitted under APPLICATION_TRACER_NAME rather than by instrumenting the transport. The
    transport is shared with the LLM vendor SDKs, and the export filter allowlists by
    instrumentation scope name, so an httpx span from our MCP client and one from the OpenAI
    SDK are the same string and cannot be told apart. Emitting the span ourselves makes the
    scope name the discriminator by construction.

    Identifiers only, never arguments or results, which carry flow data. Errors record the
    exception type, never its message, for the same reason.

    Yields an :class:`OutboundCallScope`. A caller whose protocol reports failure in the return
    value rather than by raising must call ``record_error`` or its failures export as successes.
    """
    if not _OTEL_AVAILABLE:
        yield OutboundCallScope()
        return
    tracer = trace.get_tracer(APPLICATION_TRACER_NAME)
    # Neither recording nor status-setting is delegated to the SDK: its versions write the
    # exception message onto the span, and that can carry flow data.
    with tracer.start_as_current_span(name, record_exception=False, set_status_on_exception=False) as span:
        scope = OutboundCallScope(span)
        for key, value in attributes.items():
            span.set_attribute(key, value)
        try:
            yield scope
        # BaseException, not Exception: CancelledError is a BaseException, and a tool call
        # cancelled by a client disconnect or an outer wait_for would otherwise export as a
        # success. Only the type is recorded, so this stays inside the same boundary.
        except BaseException as exc:
            error_type = _root_error_type(exc)
            span.set_status(trace.Status(trace.StatusCode.ERROR, error_type))
            span.set_attribute("error.type", error_type)
            raise
        else:
            if scope.error_type is not None:
                span.set_status(trace.Status(trace.StatusCode.ERROR, scope.error_type))
                span.set_attribute("error.type", scope.error_type)


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


def start_event_loop_lag_monitor(
    meter_provider: MeterProvider | None,
    *,
    interval: float = EVENT_LOOP_LAG_INTERVAL_SECONDS,
) -> asyncio.Task | None:
    """Record event-loop scheduling delay as a histogram on the running loop.

    This is the async-specific failure that nothing else on a dashboard explains: one
    blocking call on the loop thread stalls every endpoint at once, while CPU, memory and GC
    stay flat, so the process metrics report a healthy service while it is on fire. Sleeping
    a known interval and measuring how late we actually wake is the cheapest signal that
    separates "blocked" from "genuinely busy".

    Carries no attributes on purpose: the value describes this process, and unbounded labels
    are what make metrics expensive.

    Returns the task so the caller can stop it on shutdown, or None when there is no meter
    provider to record on (nothing configured, or OpenTelemetry not installed).
    """
    if not _OTEL_AVAILABLE or meter_provider is None:
        return None

    histogram = meter_provider.get_meter(APPLICATION_METER_NAME).create_histogram(
        EVENT_LOOP_LAG_METRIC,
        unit="s",
        description="How much later than requested the event loop resumed a sleeping task.",
        explicit_bucket_boundaries_advisory=list(EVENT_LOOP_LAG_BUCKETS_SECONDS),
    )

    async def _monitor() -> None:
        while True:
            started = time.perf_counter()
            await asyncio.sleep(interval)
            try:
                # perf_counter is monotonic, so drift cannot go negative from a clock change;
                # clamp anyway so a pathological scheduler cannot record a negative latency.
                histogram.record(max(time.perf_counter() - started - interval, 0.0))
            except Exception:  # noqa: BLE001 - a sampler must not take the app down
                # Without this the task dies silently (the metric simply stops) and the
                # exception waits on the task until shutdown awaits it, where it would
                # replace whatever was actually shutting the app down.
                logger.exception("Event loop lag sampler failed; continuing without this sample")

    return asyncio.create_task(_monitor(), name="langflow-event-loop-lag")


async def stop_event_loop_lag_monitor(task: asyncio.Task | None) -> None:
    """Cancel the monitor started by :func:`start_event_loop_lag_monitor`. Safe with None."""
    if task is None:
        return

    async def _wait_for_monitor() -> None:
        with contextlib.suppress(asyncio.CancelledError):
            await task

    task.cancel()
    # The waiter absorbs only the monitor's expected cancellation. Shielding it keeps
    # cancellation of the calling lifespan task from being forwarded into that waiter
    # and mistaken for the monitor's cancellation.
    await asyncio.shield(_wait_for_monitor())

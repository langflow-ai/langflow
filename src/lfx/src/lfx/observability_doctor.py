"""OTLP delivery self-test: build the real exporters and send one synthetic item per signal.

OTLP exporters swallow delivery failures by design. They retry, then drop, and log at most.
An operator who sets a wrong endpoint, wrong protocol, or missing auth header gets silence:
no error at startup, no data in the backend, no way to tell which end is wrong.

This module turns that silence into an answer. It resolves the same ``OTEL_*`` environment
:mod:`lfx.observability` bootstraps from, using that module's own resolution helpers so the two
cannot drift, constructs the same exporters, pushes one synthetic span, metric and log record
through each, and reports the export result along with whatever the exporter logged on the way.
Nothing global is installed: the providers built here are local and thrown away, so running the
check against a live process cannot disturb it.

The synthetic payloads are produced by the SDK itself (a real tracer, meter and logger feeding
an in-memory sink) rather than hand-constructed, so what reaches the exporter is shaped exactly
like production traffic.

Scope, deliberately: this verifies configuration and reachability from wherever it runs. It
cannot verify that a *separate* serving process installed its providers, because it runs in its
own process and builds its own. :func:`lfx.observability.bootstrap_application_telemetry`
declines to install traces or logs when another provider is already present, and a doctor run
cannot observe that. The CLI says so rather than letting a green result overclaim.
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from dataclasses import dataclass, field

from lfx.log.logger import logger
from lfx.observability import (
    APPLICATION_METER_NAME,
    APPLICATION_TRACER_NAME,
    otlp_endpoint,
    otlp_exporter_class,
    otlp_exporter_disabled,
)

SIGNALS = ("traces", "metrics", "logs")

# The name every synthetic item carries, so an operator can find it in their backend and
# confirm the round trip end to end rather than trusting an exporter's return value alone.
PROBE_NAME = "lfx.observability.doctor"

OK = "ok"
FAILED = "failed"
SKIPPED = "skipped"


@dataclass
class SignalReport:
    """The outcome of pushing one synthetic item for a single signal."""

    signal: str
    status: str = SKIPPED
    endpoint: str | None = None
    protocol: str | None = None
    detail: str = ""
    # Header names only, resolved per signal. The values are bearer tokens and API keys.
    header_keys: list[str] = field(default_factory=list)
    # Whatever the exporter logged while we held the line open. This is the whole point of the
    # command: these messages are normally emitted into a logger nobody is watching, and then
    # the failure is dropped.
    exporter_logs: list[str] = field(default_factory=list)


@dataclass
class DoctorReport:
    """The resolved configuration and the per-signal results."""

    signals: list[SignalReport] = field(default_factory=list)
    service_name: str = ""
    # Set when the check could not run at all, rather than running and failing.
    error: str = ""

    @property
    def ok(self) -> bool:
        """True when nothing failed. An all-skipped run is not a failure, it is 'not configured'."""
        return not self.error and all(s.status != FAILED for s in self.signals)

    @property
    def configured(self) -> bool:
        """Whether any signal resolved an endpoint, regardless of whether it was then disabled."""
        return any(s.endpoint for s in self.signals)


class _ExporterLogCapture(logging.Handler):
    """Collects what the OTLP exporters log, which is where swallowed failures go."""

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(f"{record.levelname}: {record.getMessage()}")


@contextmanager
def _capture_exporter_logs():
    """Listen on the ``opentelemetry`` logger for the duration of one export.

    The level is forced on that logger as well as the handler: it is normally NOTSET, so its
    effective level comes from the root, and a host that raised the root above WARNING would
    otherwise hide the very messages we are here to surface. Both are restored afterwards.
    """
    handler = _ExporterLogCapture()
    otel_logger = logging.getLogger("opentelemetry")
    previous_level = otel_logger.level
    otel_logger.setLevel(logging.WARNING)
    otel_logger.addHandler(handler)
    try:
        yield handler
    finally:
        otel_logger.removeHandler(handler)
        otel_logger.setLevel(previous_level)


def _header_keys(signal: str) -> list[str]:
    """Header names for one signal, never the values.

    Mirrors the SDK's resolution, which is a fallback and not a merge: a per-signal variable
    replaces the generic one outright for that signal. Reporting the union instead would tell an
    operator debugging "traces authenticate, metrics 401" that both carry the same headers when
    neither does.
    """
    from opentelemetry.util.re import parse_env_headers

    raw = os.getenv(f"OTEL_EXPORTER_OTLP_{signal.upper()}_HEADERS")
    if raw is None:
        raw = os.getenv("OTEL_EXPORTER_OTLP_HEADERS")
    if not raw:
        return []
    return list(parse_env_headers(raw, liberal=True))


def _probe_spans(resource):
    """One real span, produced by a throwaway tracer provider and caught in memory."""
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    sink = InMemorySpanExporter()
    # shutdown_on_exit=False: this provider is thrown away here, and registering an atexit
    # handler for it would outlive the check and accumulate across repeated calls.
    provider = TracerProvider(resource=resource, shutdown_on_exit=False)
    provider.add_span_processor(SimpleSpanProcessor(sink))
    with provider.get_tracer(APPLICATION_TRACER_NAME).start_as_current_span(PROBE_NAME):
        pass
    spans = sink.get_finished_spans()
    provider.shutdown()
    return spans


def _probe_metrics(resource, exporter):
    """One real counter data point, collected through an in-memory reader.

    The reader takes its temporality and aggregation from the exporter that is about to send the
    point, which is what ``PeriodicExportingMetricReader`` does in the real pipeline. Left at the
    reader's cumulative default, ``OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=delta`` would
    be ignored here and the doctor would test a data point shaped unlike production's, against
    backends that accept one and reject the other.
    """
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import InMemoryMetricReader

    reader = InMemoryMetricReader(
        preferred_temporality=exporter._preferred_temporality,  # noqa: SLF001
        preferred_aggregation=exporter._preferred_aggregation,  # noqa: SLF001
    )
    provider = MeterProvider(resource=resource, metric_readers=[reader], shutdown_on_exit=False)
    provider.get_meter(APPLICATION_METER_NAME).create_counter(PROBE_NAME).add(1)
    data = reader.get_metrics_data()
    provider.shutdown()
    return data


def _probe_logs(resource):
    """One real log record, emitted through a throwaway logger provider."""
    from opentelemetry._logs import SeverityNumber
    from opentelemetry.sdk._logs import LoggerProvider
    from opentelemetry.sdk._logs.export import InMemoryLogExporter, SimpleLogRecordProcessor

    sink = InMemoryLogExporter()
    provider = LoggerProvider(resource=resource, shutdown_on_exit=False)
    provider.add_log_record_processor(SimpleLogRecordProcessor(sink))
    provider.get_logger(PROBE_NAME).emit(
        body="lfx observability doctor probe",
        severity_number=SeverityNumber.INFO,
        severity_text="INFO",
    )
    records = sink.get_finished_logs()
    provider.shutdown()
    return records


def _is_empty(payload) -> bool:
    """Whether the probe produced nothing to send.

    Metrics arrive as a ``MetricsData`` rather than a sequence, so a plain truth test will not
    do. This matters because an empty payload still exports as SUCCESS, which would report
    delivery for a request that carried no data.
    """
    resource_metrics = getattr(payload, "resource_metrics", None)
    if resource_metrics is not None:
        return not resource_metrics
    return not payload


def _empty_payload_detail(signal: str) -> str:
    """Explain an empty probe, naming the sampler when that is what suppressed it."""
    if signal == "traces":
        sampler = os.getenv("OTEL_TRACES_SAMPLER", "parentbased_always_on")
        return (
            "The probe span was not recorded, so nothing could be sent and delivery was not "
            f"tested. OTEL_TRACES_SAMPLER={sampler} is dropping it."
        )
    return f"The {signal} probe produced no data to send, so delivery was not tested."


def _check_signal(signal: str, resource, timeout: float | None) -> SignalReport:
    """Push one synthetic item for *signal* and report what the transport actually did."""
    from lfx.observability import _otlp_protocol

    report = SignalReport(signal=signal, endpoint=otlp_endpoint(signal))
    if not report.endpoint:
        report.detail = (
            f"No endpoint configured. Set OTEL_EXPORTER_OTLP_{signal.upper()}_ENDPOINT or OTEL_EXPORTER_OTLP_ENDPOINT."
        )
        return report
    if otlp_exporter_disabled(signal):
        report.detail = f"Disabled by OTEL_{signal.upper()}_EXPORTER=none."
        return report

    report.protocol = _otlp_protocol(signal)
    report.header_keys = _header_keys(signal)
    route = f"{report.endpoint} over {report.protocol}"

    try:
        exporter = otlp_exporter_class(signal, report.protocol)(timeout=timeout)
    except Exception as exc:  # noqa: BLE001
        # Endpoint and protocol belong on every failure line, not only the ones that reached the
        # wire: a bad certificate path fails here, and "which end is wrong" is the question.
        report.status = FAILED
        report.detail = f"Could not build the exporter for {route}. {type(exc).__name__}: {exc}"
        return report

    if signal == "traces":
        payload = _probe_spans(resource)
    elif signal == "metrics":
        payload = _probe_metrics(resource, exporter)
    else:
        payload = _probe_logs(resource)

    if _is_empty(payload):
        report.status = FAILED
        report.detail = _empty_payload_detail(signal)
        return report

    with _capture_exporter_logs() as capture:
        try:
            result = exporter.export(payload)
        except Exception as exc:  # noqa: BLE001
            # The exporters normally catch their own transport errors, but a misconfiguration
            # that trips before the request can still raise. Surfacing it is the whole job here.
            report.status = FAILED
            report.detail = f"Export to {route} failed. {type(exc).__name__}: {exc}"
            report.exporter_logs = capture.messages
            return report
        finally:
            try:
                exporter.shutdown()
            except Exception as exc:  # noqa: BLE001
                logger.debug(f"Ignoring error while shutting down the {signal} probe exporter: {exc}")

    report.exporter_logs = capture.messages
    # Every signal's export result enum spells success as a member named SUCCESS.
    if getattr(result, "name", "") == "SUCCESS":
        report.status = OK
        report.detail = f"Accepted by {route}."
    else:
        report.status = FAILED
        # Deliberately not "rejected": a refused connection, a DNS failure and a 4xx all land
        # here, and claiming the backend answered would point the operator at the wrong end. The
        # captured exporter log printed below carries which one it actually was.
        report.detail = f"Export to {route} failed."
    return report


def run_doctor(*, timeout: float | None = None) -> DoctorReport:
    """Send a synthetic span, metric and log through the configured OTLP exporters.

    Returns a :class:`DoctorReport` describing the resolved configuration and what each signal's
    transport actually did. Installs nothing globally, so it is safe to run beside a live
    process.

    ``timeout`` overrides the per-export timeout in seconds. Left unset, the exporters use
    ``OTEL_EXPORTER_OTLP_TIMEOUT`` or their own default. Note that the exporters retry with
    backoff inside that budget, so an unreachable endpoint takes the full timeout per signal.
    """
    from lfx.observability import _OTEL_AVAILABLE

    if not _OTEL_AVAILABLE:
        return DoctorReport(
            error=(
                "OpenTelemetry is not installed, so nothing can be exported. "
                "Install it with: pip install 'lfx[otel]' (the full langflow distribution already includes it)."
            )
        )

    from opentelemetry.sdk.resources import SERVICE_NAME

    from lfx.observability import _resource

    resource = _resource()
    return DoctorReport(
        signals=[_check_signal(signal, resource, timeout) for signal in SIGNALS],
        service_name=str(resource.attributes.get(SERVICE_NAME, "")),
    )

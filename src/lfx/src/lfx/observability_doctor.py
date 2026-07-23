"""OTLP delivery self-test: build the real exporters and send one synthetic item per signal.

OTLP exporters swallow delivery failures by design. They retry, then drop, and log at most.
An operator who sets a wrong endpoint, wrong protocol, or missing auth header gets silence:
no error at startup, no data in the backend, no way to tell which end is wrong.

This module turns that silence into an answer. It resolves the same ``OTEL_*`` environment
:mod:`lfx.observability` bootstraps from, constructs the same exporters, pushes one synthetic
span, metric and log record through each, and reports the export result along with whatever
the exporter logged on the way. Nothing global is installed: the providers built here are
local and thrown away, so running the check against a live process cannot disturb it.

The synthetic payloads are produced by the SDK itself (a real tracer, meter and logger feeding
an in-memory sink) rather than hand-constructed, so what reaches the exporter is shaped exactly
like production traffic.
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from dataclasses import dataclass, field

from lfx.log.logger import logger
from lfx.observability import APPLICATION_METER_NAME, APPLICATION_TRACER_NAME

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
    # Whatever the exporter logged while we held the line open. This is the whole point of the
    # command: these messages are normally emitted into a logger nobody is watching, and then
    # the failure is dropped.
    exporter_logs: list[str] = field(default_factory=list)


@dataclass
class DoctorReport:
    """The resolved configuration and the per-signal results."""

    signals: list[SignalReport] = field(default_factory=list)
    service_name: str = ""
    # Header names only. The values are bearer tokens and API keys.
    header_keys: list[str] = field(default_factory=list)
    # Set when the check could not run at all, rather than running and failing.
    error: str = ""

    @property
    def ok(self) -> bool:
        """True when nothing failed. An all-skipped run is not a failure, it is 'not configured'."""
        return not self.error and all(s.status != FAILED for s in self.signals)


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


def _endpoint(signal: str) -> str | None:
    """Resolve the endpoint the way the SDK does: per-signal variable first, then the generic one."""
    return os.getenv(f"OTEL_EXPORTER_OTLP_{signal.upper()}_ENDPOINT") or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")


def _exporter_disabled(signal: str) -> bool:
    """Whether the operator turned this signal off while leaving a shared endpoint set."""
    return os.getenv(f"OTEL_{signal.upper()}_EXPORTER", "otlp").strip().lower() == "none"


def _header_keys() -> list[str]:
    """Header names across the generic and per-signal variables, never the values."""
    from opentelemetry.util.re import parse_env_headers

    names: list[str] = []
    variables = ["OTEL_EXPORTER_OTLP_HEADERS"] + [f"OTEL_EXPORTER_OTLP_{s.upper()}_HEADERS" for s in SIGNALS]
    for variable in variables:
        raw = os.getenv(variable)
        if not raw:
            continue
        names.extend(key for key in parse_env_headers(raw, liberal=True) if key not in names)
    return names


def _probe_spans(resource):
    """One real span, produced by a throwaway tracer provider and caught in memory."""
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    sink = InMemorySpanExporter()
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(SimpleSpanProcessor(sink))
    with provider.get_tracer(APPLICATION_TRACER_NAME).start_as_current_span(PROBE_NAME):
        pass
    return sink.get_finished_spans()


def _probe_metrics(resource):
    """One real counter data point, collected through an in-memory reader."""
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import InMemoryMetricReader

    reader = InMemoryMetricReader()
    # shutdown_on_exit=False: this provider is thrown away here, and registering an atexit
    # handler for it would outlive the check.
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
    provider.shutdown()
    return sink.get_finished_logs()


def _build_exporter(signal: str, protocol: str, timeout: float | None):
    """Construct the same exporter the bootstrap would, honoring the resolved protocol.

    Endpoint, headers, compression and certificates are left to the exporter to read from the
    environment, exactly as :mod:`lfx.observability` does, so the check exercises the operator's
    real configuration rather than a reconstruction of it.
    """
    if signal == "traces":
        if protocol == "grpc":
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter as Exporter
        else:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter as Exporter
    elif signal == "metrics":
        if protocol == "grpc":
            from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter as Exporter
        else:
            from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter as Exporter
    elif protocol == "grpc":
        from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter as Exporter
    else:
        from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter as Exporter

    # timeout=None would be passed through as an explicit override on some exporters, so only
    # pass it when the operator asked for one. Otherwise OTEL_EXPORTER_OTLP_TIMEOUT wins.
    return Exporter(timeout=timeout) if timeout is not None else Exporter()


def _check_signal(signal: str, resource, timeout: float | None) -> SignalReport:
    """Push one synthetic item for *signal* and report what the transport actually did."""
    from lfx.observability import _otlp_protocol

    report = SignalReport(signal=signal, endpoint=_endpoint(signal))
    if not report.endpoint:
        report.detail = (
            f"No endpoint configured. Set OTEL_EXPORTER_OTLP_{signal.upper()}_ENDPOINT or OTEL_EXPORTER_OTLP_ENDPOINT."
        )
        return report
    if _exporter_disabled(signal):
        report.detail = f"Disabled by OTEL_{signal.upper()}_EXPORTER=none."
        return report

    report.protocol = _otlp_protocol(signal)

    try:
        exporter = _build_exporter(signal, report.protocol, timeout)
    except Exception as exc:  # noqa: BLE001
        report.status = FAILED
        report.detail = f"Could not construct the exporter: {type(exc).__name__}: {exc}"
        return report

    payload = {"traces": _probe_spans, "metrics": _probe_metrics, "logs": _probe_logs}[signal](resource)

    with _capture_exporter_logs() as capture:
        try:
            result = exporter.export(payload)
        except Exception as exc:  # noqa: BLE001
            # The exporters normally catch their own transport errors, but a misconfiguration
            # that trips before the request (an unparseable endpoint, bad credentials) can
            # still raise. Surfacing it is the whole job here.
            report.status = FAILED
            report.detail = f"{type(exc).__name__}: {exc}"
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
        report.detail = f"Accepted by {report.endpoint} over {report.protocol}."
    else:
        report.status = FAILED
        report.detail = (
            f"{report.endpoint} rejected the export over {report.protocol} (result: {getattr(result, 'name', result)})."
        )
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

    from lfx.observability import _resource

    resource = _resource()
    from opentelemetry.sdk.resources import SERVICE_NAME

    return DoctorReport(
        signals=[_check_signal(signal, resource, timeout) for signal in SIGNALS],
        service_name=str(resource.attributes.get(SERVICE_NAME, "")),
        header_keys=_header_keys(),
    )

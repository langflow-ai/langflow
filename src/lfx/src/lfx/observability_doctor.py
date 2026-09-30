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
import threading
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
    """Collects what the OTLP exporters log, which is where swallowed failures go.

    Bound to the thread that opened the window. The ``opentelemetry`` logger is process-global, so
    beside a live server a BatchSpanProcessor failing on its own background thread would otherwise
    be collected here and printed underneath one of the doctor's own signals, blaming this run for
    an unrelated outage.
    """

    def __init__(self, thread_id: int) -> None:
        super().__init__(level=logging.WARNING)
        self.messages: list[str] = []
        self._thread_id = thread_id

    def emit(self, record: logging.LogRecord) -> None:
        if record.thread != self._thread_id:
            return
        self.messages.append(f"{record.levelname}: {record.getMessage()}")


# Serializes the temporary mutation of the process-global ``opentelemetry`` logger below.
# Without it, two overlapping capture windows snapshot each other's temporary level and restore
# out of order, leaving the logger permanently at the wrong level: a host that had quieted otel
# to ERROR is left at WARNING for the rest of the process. That would break the guarantee this
# module rests on, that a doctor run cannot disturb a live process.
#
# ponytail: one global lock, because the thing being guarded is itself one global logger. The
# windows are short and never nested, so there is nothing to contend over and no upgrade path
# worth building.
_LOGGER_STATE_LOCK = threading.Lock()


@contextmanager
def _capture_exporter_logs():
    """Listen on the ``opentelemetry`` logger for the duration of one export.

    The logger is normally NOTSET, taking its effective level from the root, so a host that
    quieted otel would hide the very messages we exist to surface. The level is therefore lowered
    to WARNING when it sits above that, and only lowered: raising it would suppress DEBUG and INFO
    records a host had deliberately asked for. Level and handler are both restored afterwards,
    under a lock so concurrent callers cannot interleave their snapshot and restore.

    Lowering it does mean a host that quieted otel to ERROR sees warnings through its own handlers
    for the length of one export. That is accepted deliberately: capturing the message the
    exporter would otherwise swallow is the entire purpose of this command, and it cannot be read
    without letting the record past the logger.
    """
    handler = _ExporterLogCapture(threading.get_ident())
    otel_logger = logging.getLogger("opentelemetry")
    with _LOGGER_STATE_LOCK:
        previous_level = otel_logger.level
        if otel_logger.getEffectiveLevel() > logging.WARNING:
            otel_logger.setLevel(logging.WARNING)
        otel_logger.addHandler(handler)
        try:
            yield handler
        finally:
            otel_logger.removeHandler(handler)
            otel_logger.setLevel(previous_level)


# What the OTLP response carries per signal when the backend accepted the request but threw
# some of the payload away. The field names differ per signal, so they are mapped once here.
_PARTIAL_SUCCESS_FIELD = {
    "traces": "rejected_spans",
    "metrics": "rejected_data_points",
    "logs": "rejected_log_records",
}


def _response_class(signal: str):
    """The protobuf response type a collector returns for *signal*."""
    if signal == "traces":
        from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceResponse as Response
    elif signal == "metrics":
        from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import (
            ExportMetricsServiceResponse as Response,
        )
    else:
        from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import ExportLogsServiceResponse as Response
    return Response


def _recording_session():
    """A requests session that keeps the last response, so we can inspect what the exporter ignored.

    The HTTP exporter decides success on ``resp.ok`` alone: it never looks at redirects and never
    parses the body. That makes several "delivered nothing" situations indistinguishable from a
    real success, which is exactly what this command exists to tell apart. Keeping the response
    lets :func:`_delivery_problem` apply the checks the exporter skips.
    """
    import requests

    class RecordingSession(requests.Session):
        def __init__(self) -> None:
            super().__init__()
            self.last_response = None

        def post(self, *args, **kwargs):
            response = super().post(*args, **kwargs)
            self.last_response = response
            return response

    return RecordingSession()


def _delivery_problem(session, signal: str) -> str | None:
    """Why a 2xx did not actually mean delivery, or None when it did.

    Three cases the exporter reports as success:

    - A redirect. ``requests`` follows a 302 by downgrading POST to GET and dropping the body, so
      an auth proxy or an ingress with a trailing-slash rule swallows the payload and answers 200
      from a login page.
    - A partial success. The collector accepted the request and then rejected some or all of the
      items, for quota, cardinality or an unknown tenant. The count is in the response body, which
      the exporter never reads.
    - A non-OTLP 200. An ingress answering HTML on an unmatched path looks identical to a
      collector otherwise. An empty body stays acceptable: real collectors send one.
    """
    response = getattr(session, "last_response", None)
    if response is None:
        return None

    if response.history:
        chain = " -> ".join(str(r.status_code) for r in response.history)
        return (
            f"the request was redirected ({chain}) to {response.url} and the payload was dropped; "
            f"redirects turn the POST into a GET, so nothing was delivered"
        )

    body = response.content
    if not body:
        return None

    try:
        parsed = _response_class(signal).FromString(body)
    except Exception:  # noqa: BLE001
        content_type = response.headers.get("Content-Type", "unknown")
        return (
            f"the endpoint answered {response.status_code} with a {content_type} body that is not an "
            f"OTLP response, so it is not a collector"
        )

    rejected = getattr(parsed.partial_success, _PARTIAL_SUCCESS_FIELD[signal], 0)
    if rejected:
        reason = parsed.partial_success.error_message or "no reason given"
        return f"the collector rejected {rejected} item(s) from it: {reason}"
    return None


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
    """One real span, produced by a throwaway tracer provider and caught in memory.

    The probe is forced to record, rather than inheriting ``OTEL_TRACES_SAMPLER``. The probe is a
    single root span with a fresh trace id, so under any probabilistic sampler it is dropped at
    the configured ratio and the traces verdict becomes a coin flip on a perfectly healthy
    pipeline: at ratio 0.1 the command fails roughly nine runs in ten and its exit code changes
    with no configuration change, which makes it useless as a healthcheck. Sampling governs which
    production traffic is worth keeping; it says nothing about whether the transport works, and
    the transport is what this command tests.

    ``always_off`` is the exception and stays inherited. There the operator has turned tracing off
    outright, so reporting that nothing was sent is the honest answer rather than a coin flip.
    """
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
    from opentelemetry.sdk.trace.sampling import ALWAYS_ON

    sink = InMemorySpanExporter()
    configured_sampler = os.getenv("OTEL_TRACES_SAMPLER", "").strip().lower()
    sampler = None if "always_off" in configured_sampler else ALWAYS_ON
    # shutdown_on_exit=False: this provider is thrown away here, and registering an atexit
    # handler for it would outlive the check and accumulate across repeated calls.
    provider = TracerProvider(resource=resource, shutdown_on_exit=False, sampler=sampler)
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


def _sdk_disabled() -> bool:
    """Whether OTEL_SDK_DISABLED turned the whole SDK into no-ops."""
    return os.getenv("OTEL_SDK_DISABLED", "").strip().lower() == "true"


def _empty_payload_detail(signal: str) -> str:
    """Explain an empty probe, naming the sampler only when one is actually configured."""
    sampler = os.getenv("OTEL_TRACES_SAMPLER", "").strip()
    if signal == "traces" and sampler:
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
    if _sdk_disabled():
        # The SDK hands back NoOp providers, so every probe comes back empty. Without this the
        # run reports three failures and blames the sampler, which is not set and drops nothing.
        report.detail = "Disabled by OTEL_SDK_DISABLED=true."
        return report

    report.protocol = _otlp_protocol(signal)
    report.header_keys = _header_keys(signal)
    route = f"{report.endpoint} over {report.protocol}"

    # Only the HTTP exporters take a session. gRPC gives no equivalent hook, so the extra
    # delivery checks below are HTTP-only and a gRPC run keeps the plain result-code verdict.
    session = None if report.protocol == "grpc" else _recording_session()
    try:
        exporter_class = otlp_exporter_class(signal, report.protocol)
        exporter = (
            exporter_class(timeout=timeout) if session is None else exporter_class(timeout=timeout, session=session)
        )
    except Exception as exc:  # noqa: BLE001
        # Endpoint and protocol belong on every failure line, not only the ones that reached the
        # wire: a malformed OTEL_EXPORTER_OTLP_TIMEOUT raises here, before any request exists, and
        # "which end is wrong" is still the question. (A bad certificate path does not: both
        # transports construct fine and fail later, which the export branch below covers.)
        report.status = FAILED
        report.detail = f"Could not build the exporter for {route}. {type(exc).__name__}: {exc}"
        return report

    # Report the URL the exporter resolved, not the raw variable. Only the generic endpoint gets
    # /v1/<signal> appended; a per-signal one is used verbatim. Without this a per-signal endpoint
    # aimed at the wrong path prints the same string on a failing and a passing line, so the
    # operator sees opposite verdicts against what looks like one URL.
    resolved = getattr(exporter, "_endpoint", None)
    if resolved:
        report.endpoint = str(resolved)
        route = f"{report.endpoint} over {report.protocol}"

    try:
        if signal == "traces":
            payload = _probe_spans(resource)
        elif signal == "metrics":
            payload = _probe_metrics(resource, exporter)
        else:
            payload = _probe_logs(resource)
    except Exception as exc:  # noqa: BLE001
        # The probe builds SDK objects from environment the operator controls, so a bad value can
        # raise here. One failed signal is a better answer than an aborted run that reports none.
        #
        # Note this cannot catch the OTEL_*_LIMIT family: the SDK parses those into module-level
        # constants at import, so a malformed one raises while lfx.observability is being imported,
        # long before this runs. Nothing here can report that, and it is not worth chasing because
        # the same variable stops bootstrap_application_telemetry too, so the server would not
        # have started either.
        report.status = FAILED
        report.detail = f"Could not build the {signal} probe. {type(exc).__name__}: {exc}"
        return report

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
        # SUCCESS only means the exporter saw a status under 400. It never checks whether it was
        # redirected away from the collector, and never reads the response body, so several
        # "delivered nothing" cases reach here looking identical to a real success.
        problem = _delivery_problem(session, signal) if session is not None else None
        if problem:
            report.status = FAILED
            report.detail = f"Export to {route} reported success but {problem}."
            return report
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

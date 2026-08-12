"""The OTLP doctor reports what the transport actually did, instead of swallowing it.

These run in-process, unlike the bootstrap tests next door: the doctor deliberately installs no
global providers, so there is no process-global state to isolate in a subprocess.

Every check here goes through a real HTTP server rather than a stubbed exporter. The whole
point of the command is what the transport does, so a test that faked the transport would
assert nothing worth knowing.

OpenTelemetry is an optional lfx extra (``lfx[otel]``), so the no-otel path is asserted first
and the rest skip when the extra is absent.
"""

import importlib.util
import logging
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

import pytest
from lfx.observability_doctor import FAILED, OK, SKIPPED, run_doctor

_HAS_OTEL = importlib.util.find_spec("opentelemetry") is not None
requires_otel = pytest.mark.skipif(not _HAS_OTEL, reason="requires the lfx[otel] extra")

OTLP_PATHS = {"/v1/traces", "/v1/metrics", "/v1/logs"}


class _CollectorStub:
    """A real HTTP server answering the three OTLP signal paths with a fixed status."""

    def __init__(self, status: int = 200) -> None:
        self.status = status
        # (path, headers, body_length). Recorded rather than asserted in the handler: an assert
        # raised on the server thread is routed to socketserver's handle_error, the client still
        # sees its response, and the test passes regardless. Assertions belong on the test thread.
        self.received: list[tuple[str, dict[str, str], int]] = []
        # Default is an empty body, which real collectors do send and which the doctor accepts.
        # Tests needing a partial-success or non-OTLP response set these before running.
        self.response_body = b""
        self.response_content_type = "application/x-protobuf"
        stub = self
        received = self.received
        status_code = status

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                received.append((self.path, dict(self.headers), len(body)))
                payload = stub.response_body
                self.send_response(status_code)
                self.send_header("Content-Type", stub.response_content_type)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                if payload:
                    self.wfile.write(payload)

            def log_message(self, *_args) -> None:
                """Silence the default stderr access log."""

        self._server = HTTPServer(("127.0.0.1", 0), Handler)
        self.endpoint = f"http://127.0.0.1:{self._server.server_port}"

    def __enter__(self) -> "_CollectorStub":
        self._thread = Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)

    def close_without_serving(self) -> None:
        """Release the bound port without ever serving, so connections to it reliably refuse."""
        self._server.server_close()

    @property
    def paths(self) -> set[str]:
        return {path for path, _headers, _length in self.received}

    def body_length(self, path: str) -> int:
        return next(length for received_path, _headers, length in self.received if received_path == path)

    def headers_for(self, path: str) -> dict[str, str]:
        return next(headers for received_path, headers, _length in self.received if received_path == path)


@pytest.fixture
def clean_otel_env(monkeypatch):
    """Drop the developer's own OTEL_* vars so their APM config cannot skew a result."""
    for name in [key for key in os.environ if key.startswith("OTEL_")]:
        monkeypatch.delenv(name, raising=False)


def _by_signal(report):
    return {signal.signal: signal for signal in report.signals}


def test_reports_the_missing_extra_rather_than_a_silent_pass(monkeypatch):
    """Without otel there is nothing to test, and saying 'ok' would be a lie."""
    import lfx.observability

    monkeypatch.setattr(lfx.observability, "_OTEL_AVAILABLE", False)
    report = run_doctor()

    assert "lfx[otel]" in report.error
    assert not report.ok
    assert report.signals == []


@requires_otel
@pytest.mark.usefixtures("clean_otel_env")
def test_no_endpoint_skips_every_signal():
    """Nothing configured is 'not set up', not a failure; but it must not claim delivery either."""
    report = run_doctor()

    assert [signal.status for signal in report.signals] == [SKIPPED] * 3
    assert all("No endpoint configured" in signal.detail for signal in report.signals)
    # Nothing failed, so ok stays True. The CLI is what turns an all-skipped run into exit 1.
    assert report.ok
    assert not report.configured


@requires_otel
@pytest.mark.usefixtures("clean_otel_env")
def test_delivers_all_three_signals_to_a_live_endpoint(monkeypatch):
    """The success path has to be a real round trip, or it proves nothing about delivery."""
    with _CollectorStub(status=200) as collector:
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", collector.endpoint)
        report = run_doctor(timeout=5)

        assert report.ok
        assert [signal.status for signal in report.signals] == [OK] * 3
        # Each signal must reach its own path; a doctor that posted everything to /v1/traces
        # would pass while metrics and logs silently went nowhere.
        assert collector.paths == OTLP_PATHS
        # And each request must actually carry a payload. An empty body still returns 200.
        for path in OTLP_PATHS:
            assert collector.body_length(path) > 0, f"{path} received an empty payload"


@requires_otel
@pytest.mark.usefixtures("clean_otel_env")
def test_a_sampler_that_drops_the_probe_is_not_reported_as_delivered(monkeypatch):
    """A non-recording probe span means nothing was sent, and OK there is the worst failure mode.

    OTEL_TRACES_SAMPLER=always_off makes the probe span non-recording, so the batch is empty.
    An empty OTLP request still returns 200, so without an explicit guard the command reports
    delivery and tells the operator to go look for an item that was never sent.
    """
    with _CollectorStub(status=200) as collector:
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", collector.endpoint)
        monkeypatch.setenv("OTEL_TRACES_SAMPLER", "always_off")
        report = run_doctor(timeout=5)

        traces = _by_signal(report)["traces"]
        assert traces.status == FAILED
        assert "OTEL_TRACES_SAMPLER=always_off" in traces.detail
        assert not report.ok
        # Nothing should have been posted to the traces path at all.
        assert "/v1/traces" not in collector.paths
        # The other two signals are unaffected by the trace sampler.
        assert _by_signal(report)["metrics"].status == OK
        assert _by_signal(report)["logs"].status == OK


@requires_otel
@pytest.mark.usefixtures("clean_otel_env")
def test_metric_probe_uses_the_configured_temporality(monkeypatch):
    """A cumulative probe against a delta-only backend passes while production is rejected.

    PeriodicExportingMetricReader takes its temporality from the exporter, so the runtime sends
    delta when asked to. A probe left on InMemoryMetricReader's cumulative default would test a
    differently shaped point than the one production sends.
    """
    from lfx.observability import _resource
    from lfx.observability_doctor import _probe_metrics
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
    from opentelemetry.sdk.metrics import Counter

    monkeypatch.setenv("OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE", "delta")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://127.0.0.1:4318")

    exporter = OTLPMetricExporter()
    data = _probe_metrics(_resource(), exporter)
    point = data.resource_metrics[0].scope_metrics[0].metrics[0].data

    assert point.aggregation_temporality == exporter._preferred_temporality[Counter]


@requires_otel
@pytest.mark.usefixtures("clean_otel_env")
def test_surfaces_the_rejection_the_exporter_would_have_swallowed(monkeypatch):
    """The reason this command exists: a 401 must become visible text, not a dropped batch."""
    with _CollectorStub(status=401) as collector:
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", collector.endpoint)
        report = run_doctor(timeout=5)

        assert not report.ok
        assert [signal.status for signal in report.signals] == [FAILED] * 3
        traces = _by_signal(report)["traces"]
        assert collector.endpoint in traces.detail
        # The status code is what tells the operator it is auth and not the endpoint.
        assert any("401" in message for message in traces.exporter_logs), traces.exporter_logs


@requires_otel
@pytest.mark.usefixtures("clean_otel_env")
def test_unreachable_endpoint_names_the_transport_error(monkeypatch):
    """A wrong port must read as a connection failure, not as silence."""
    # Bound and immediately closed, so the port is real and reliably refuses.
    closed = _CollectorStub()
    closed.close_without_serving()
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", closed.endpoint)

    report = run_doctor(timeout=2)

    assert not report.ok
    traces = _by_signal(report)["traces"]
    assert traces.status == FAILED
    assert traces.exporter_logs, "the transport error must be surfaced, not dropped"


@requires_otel
@pytest.mark.usefixtures("clean_otel_env")
def test_every_failure_names_the_endpoint_and_protocol(monkeypatch):
    """Which end is wrong is the question, so the route belongs on failures that never sent.

    An unreadable certificate path fails when the export is attempted rather than when the
    exporter is built, so this covers the raise-during-export branch.
    """
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "https://127.0.0.1:4318")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_CERTIFICATE", "/nonexistent/ca.pem")

    report = run_doctor(timeout=2)

    for signal in report.signals:
        assert signal.status == FAILED
        assert "127.0.0.1:4318" in signal.detail, signal.detail
        assert signal.protocol in signal.detail, signal.detail


@requires_otel
@pytest.mark.usefixtures("clean_otel_env")
def test_an_unbuildable_exporter_is_reported_with_its_route(monkeypatch):
    """The other failure branch: the exporter cannot even be constructed.

    A malformed OTEL_EXPORTER_OTLP_TIMEOUT is a plausible operator typo and raises inside the
    constructor, before any probe payload exists. That path must name the endpoint, the
    protocol and the underlying error rather than reporting a bare exception.
    """
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://127.0.0.1:4318")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TIMEOUT", "abc")

    report = run_doctor()

    assert not report.ok
    for signal in report.signals:
        assert signal.status == FAILED
        assert "Could not build the exporter" in signal.detail, signal.detail
        assert "127.0.0.1:4318" in signal.detail, signal.detail
        assert signal.protocol in signal.detail, signal.detail
        assert "abc" in signal.detail, signal.detail


@requires_otel
@pytest.mark.usefixtures("clean_otel_env")
def test_per_signal_disable_is_reported_as_disabled_not_broken(monkeypatch):
    """OTEL_TRACES_EXPORTER=none is a deliberate choice and must not read as a failure."""
    with _CollectorStub(status=200) as collector:
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", collector.endpoint)
        monkeypatch.setenv("OTEL_TRACES_EXPORTER", "none")
        report = run_doctor(timeout=5)

        signals = _by_signal(report)
        assert signals["traces"].status == SKIPPED
        assert "OTEL_TRACES_EXPORTER=none" in signals["traces"].detail
        assert signals["metrics"].status == OK
        assert signals["logs"].status == OK
        assert report.ok
        assert "/v1/traces" not in collector.paths


@requires_otel
@pytest.mark.usefixtures("clean_otel_env")
def test_disabled_everywhere_is_distinguishable_from_unconfigured(monkeypatch):
    """An endpoint with every signal off is a deliberate setup, not a missing endpoint.

    Both render as SKIPPED, so the summary has to key off whether an endpoint resolved at all,
    or it contradicts the three lines printed above it.
    """
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://127.0.0.1:4318")
    for signal in ("TRACES", "METRICS", "LOGS"):
        monkeypatch.setenv(f"OTEL_{signal}_EXPORTER", "none")

    report = run_doctor(timeout=2)

    assert [signal.status for signal in report.signals] == [SKIPPED] * 3
    # This is what separates the two summaries in the CLI.
    assert report.configured


@requires_otel
@pytest.mark.usefixtures("clean_otel_env")
def test_per_signal_endpoint_overrides_the_generic_one(monkeypatch):
    """Per-signal endpoints are how operators split backends; resolving them wrong hides a whole signal."""
    with _CollectorStub(status=200) as generic, _CollectorStub(status=200) as logs_only:
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", generic.endpoint)
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_LOGS_ENDPOINT", logs_only.endpoint)
        report = run_doctor(timeout=5)

        assert report.ok
        assert generic.paths == {"/v1/traces", "/v1/metrics"}
        # Per the OTLP spec a per-signal endpoint is used verbatim; only the generic one gets
        # the signal path appended. Landing on "/" here is the SDK behaving correctly, and is
        # exactly the resolution the bootstrap performs.
        assert logs_only.paths == {"/"}


@requires_otel
@pytest.mark.usefixtures("clean_otel_env")
def test_headers_are_sent_but_their_values_are_never_reported(monkeypatch):
    """Header values are bearer tokens; the report is something operators paste into tickets."""
    with _CollectorStub(status=200) as collector:
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", collector.endpoint)
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_HEADERS", "api-key=super-secret-value")
        report = run_doctor(timeout=5)

        assert all(signal.header_keys == ["api-key"] for signal in report.signals)
        # The header must actually reach the wire, otherwise a passing doctor would not prove auth works.
        assert collector.headers_for("/v1/traces").get("api-key") == "super-secret-value"

        rendered = f"{[s.header_keys for s in report.signals]}{[s.detail for s in report.signals]}"
        assert "super-secret-value" not in rendered


@requires_otel
@pytest.mark.usefixtures("clean_otel_env")
def test_per_signal_headers_replace_the_generic_ones_rather_than_merging(monkeypatch):
    """The SDK falls back, it does not merge, so a merged report points at the wrong end.

    An operator debugging "traces authenticate, metrics 401" needs to see that metrics carries
    the generic header and traces carries only its own.
    """
    with _CollectorStub(status=200) as collector:
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", collector.endpoint)
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_HEADERS", "x-generic=g")
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_HEADERS", "authorization=t")
        report = run_doctor(timeout=5)

        signals = _by_signal(report)
        assert signals["traces"].header_keys == ["authorization"]
        assert signals["metrics"].header_keys == ["x-generic"]

        # And that is what actually went over the wire.
        traces_headers = collector.headers_for("/v1/traces")
        assert traces_headers.get("authorization") == "t"
        assert "x-generic" not in traces_headers
        assert collector.headers_for("/v1/metrics").get("x-generic") == "g"


class _RedirectingStub:
    """A stub that 302s the OTLP POST to a login page, like an auth proxy in front of a collector."""

    def __init__(self) -> None:
        self.saw: list[str] = []
        saw = self.saw

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                self.rfile.read(int(self.headers.get("Content-Length", 0)))
                saw.append(f"POST {self.path}")
                self.send_response(302)
                self.send_header("Location", "/login")
                self.send_header("Content-Length", "0")
                self.end_headers()

            def do_GET(self) -> None:
                saw.append(f"GET {self.path}")
                page = b"<html>login</html>"
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(page)))
                self.end_headers()
                self.wfile.write(page)

            def log_message(self, *_args) -> None:
                """Silence the default stderr access log."""

        self._server = HTTPServer(("127.0.0.1", 0), Handler)
        self.endpoint = f"http://127.0.0.1:{self._server.server_port}"

    def __enter__(self) -> "_RedirectingStub":
        self._thread = Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)


@requires_otel
@pytest.mark.usefixtures("clean_otel_env")
def test_a_redirected_export_is_not_reported_as_delivered(monkeypatch):
    """A 302 turns the POST into a GET and drops the payload, but the exporter still says SUCCESS.

    An auth proxy or an ingress redirect rule in front of the collector produces exactly this:
    the body never arrives, the login page answers 200, and the exporter reports success because
    it only looks at the status code. Reporting OK here sends the operator away from the problem.
    """
    with _RedirectingStub() as stub:
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", stub.endpoint)
        report = run_doctor(timeout=5)

        assert not report.ok
        for signal in report.signals:
            assert signal.status == FAILED, signal.detail
            assert "redirected" in signal.detail, signal.detail
        # The payload really was thrown away: each POST became a GET of the login page.
        assert "GET /login" in stub.saw


@requires_otel
@pytest.mark.usefixtures("clean_otel_env")
def test_a_partial_success_response_is_not_reported_as_delivered(monkeypatch):
    """A collector can answer 200 and still reject the items, for quota or an unknown tenant.

    The count lives in the OTLP response body, which the exporter never reads.
    """
    from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceResponse

    rejected = ExportTraceServiceResponse()
    rejected.partial_success.rejected_spans = 1
    rejected.partial_success.error_message = "quota exceeded"
    body = rejected.SerializeToString()

    with _CollectorStub(status=200) as collector:
        collector.response_body = body
        collector.response_content_type = "application/x-protobuf"
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", f"{collector.endpoint}/v1/traces")
        report = run_doctor(timeout=5)

        traces = _by_signal(report)["traces"]
        assert traces.status == FAILED, traces.detail
        assert "rejected 1 item" in traces.detail, traces.detail
        assert "quota exceeded" in traces.detail, traces.detail


@requires_otel
@pytest.mark.usefixtures("clean_otel_env")
def test_a_non_otlp_200_is_not_reported_as_delivered(monkeypatch):
    """An ingress answering HTML on an unmatched path looks like a collector to the exporter."""
    with _CollectorStub(status=200) as collector:
        collector.response_body = b"<html>not a collector</html>"
        collector.response_content_type = "text/html"
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", collector.endpoint)
        report = run_doctor(timeout=5)

        assert not report.ok
        for signal in report.signals:
            assert signal.status == FAILED, signal.detail
            assert "not an OTLP response" in signal.detail, signal.detail


@requires_otel
@pytest.mark.usefixtures("clean_otel_env")
def test_a_probabilistic_sampler_does_not_decide_the_traces_verdict(monkeypatch):
    """Sampling governs which production traffic is kept; it says nothing about the transport.

    The probe is one root span with a fresh trace id, so an inherited ratio sampler drops it at
    that ratio and the verdict becomes a coin flip on a healthy pipeline. Repeated here because a
    single run passing proves nothing about a probabilistic bug.
    """
    with _CollectorStub(status=200) as collector:
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", collector.endpoint)
        monkeypatch.setenv("OTEL_TRACES_SAMPLER", "traceidratio")
        monkeypatch.setenv("OTEL_TRACES_SAMPLER_ARG", "0.05")

        for _ in range(10):
            traces = _by_signal(run_doctor(timeout=5))["traces"]
            assert traces.status == OK, traces.detail


@requires_otel
@pytest.mark.usefixtures("clean_otel_env")
def test_sampling_off_entirely_is_still_reported_honestly(monkeypatch):
    """always_off is a deliberate 'trace nothing', so claiming delivery would be a lie."""
    with _CollectorStub(status=200) as collector:
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", collector.endpoint)
        monkeypatch.setenv("OTEL_TRACES_SAMPLER", "always_off")
        report = run_doctor(timeout=5)

        traces = _by_signal(report)["traces"]
        assert traces.status == FAILED
        assert "always_off" in traces.detail


@requires_otel
@pytest.mark.usefixtures("clean_otel_env")
def test_sdk_disabled_is_named_as_the_cause(monkeypatch):
    """OTEL_SDK_DISABLED makes every provider a no-op, so blaming the sampler is a fabricated cause."""
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://127.0.0.1:4318")
    monkeypatch.setenv("OTEL_SDK_DISABLED", "true")

    report = run_doctor(timeout=2)

    assert [signal.status for signal in report.signals] == [SKIPPED] * 3
    for signal in report.signals:
        assert "OTEL_SDK_DISABLED" in signal.detail
        assert "SAMPLER" not in signal.detail.upper(), signal.detail


@requires_otel
def test_concurrent_capture_windows_restore_the_logger_level():
    """Overlapping capture windows must not leave the global otel logger at the wrong level.

    The capture temporarily raises the ``opentelemetry`` logger to WARNING. Two windows
    overlapping means the second snapshots the first's temporary value and restores that
    instead of the original, permanently quieting or unquieting otel for the whole process.
    Interleaved deliberately: A enters, B enters, A exits, B exits.
    """
    import threading
    import time

    from lfx.observability_doctor import _capture_exporter_logs

    otel_logger = logging.getLogger("opentelemetry")
    original = otel_logger.level
    otel_logger.setLevel(logging.ERROR)  # a host that deliberately quieted otel
    handlers_before = list(otel_logger.handlers)
    try:

        def hold(duration):
            with _capture_exporter_logs():
                time.sleep(duration)

        first = threading.Thread(target=hold, args=(0.2,))
        second = threading.Thread(target=hold, args=(0.4,))
        first.start()
        time.sleep(0.05)
        second.start()
        first.join()
        second.join()

        assert otel_logger.level == logging.ERROR, (
            f"logger left at {logging.getLevelName(otel_logger.level)} instead of ERROR"
        )
        # The handler must come off too. Restoring only the level would still leak a capture
        # handler per run, and each one keeps collecting records for the life of the process.
        assert otel_logger.handlers == handlers_before
    finally:
        otel_logger.setLevel(original)


@requires_otel
def test_capture_ignores_records_from_other_threads():
    """A live server's background exporter must not have its failures attributed to this run.

    The opentelemetry logger is process-global, so without a thread filter a BatchSpanProcessor
    failing on its own thread lands in exporter_logs and prints under one of the doctor's signals,
    blaming this check for an unrelated outage.
    """
    import threading

    from lfx.observability_doctor import _capture_exporter_logs

    otel_logger = logging.getLogger("opentelemetry")
    with _capture_exporter_logs() as capture:
        otel_logger.warning("from the doctor's own thread")
        other = threading.Thread(target=lambda: otel_logger.warning("from an unrelated thread"))
        other.start()
        other.join()

    joined = " ".join(capture.messages)
    assert "from the doctor's own thread" in joined
    assert "unrelated thread" not in joined, capture.messages


@requires_otel
@pytest.mark.usefixtures("clean_otel_env")
def test_service_name_follows_the_otel_environment(monkeypatch):
    """The operator searches their backend by service.name, so the report must show the real one."""
    with _CollectorStub(status=200) as collector:
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", collector.endpoint)
        monkeypatch.setenv("OTEL_SERVICE_NAME", "checkout-api")
        report = run_doctor(timeout=5)

        assert report.service_name == "checkout-api"


@requires_otel
@pytest.mark.usefixtures("clean_otel_env")
def test_the_doctor_installs_nothing_globally(monkeypatch):
    """It has to be safe to run beside a live process; hijacking a global provider is not.

    All three providers are checked, not just traces. A leaked meter or logger provider would be
    worse than a leaked tracer: the bootstrap reuses an already-installed one, so the server would
    silently keep the doctor's throwaway provider and export no metrics or logs at all.
    """
    import atexit

    from opentelemetry import _logs, metrics, trace

    before_tracer = trace.get_tracer_provider()
    before_meter = metrics.get_meter_provider()
    before_logger = _logs.get_logger_provider()
    atexit_before = atexit._ncallbacks()

    with _CollectorStub(status=200) as collector:
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", collector.endpoint)
        run_doctor(timeout=5)
        run_doctor(timeout=5)

    assert trace.get_tracer_provider() is before_tracer
    assert metrics.get_meter_provider() is before_meter
    assert _logs.get_logger_provider() is before_logger
    # Throwaway providers must not register atexit handlers that outlive the check.
    assert atexit._ncallbacks() == atexit_before

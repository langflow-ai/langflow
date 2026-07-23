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
        self.received: list[tuple[str, dict[str, str]]] = []
        received = self.received
        status_code = status

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                received.append((self.path, dict(self.headers)))
                # A zero-length body keeps the exporter from waiting on a protobuf response it
                # does not need in order to read the status.
                self.send_response(status_code)
                self.send_header("Content-Length", "0")
                self.end_headers()
                assert body  # a signal with an empty payload would make the check meaningless

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
        return {path for path, _headers in self.received}


@pytest.fixture
def clean_otel_env(monkeypatch):
    """Drop the developer's own OTEL_* vars so their APM config cannot skew a result."""
    import os

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

        assert report.header_keys == ["api-key"]
        # The header must actually reach the wire, otherwise a passing doctor would not prove auth works.
        _path, headers = collector.received[0]
        assert headers.get("api-key") == "super-secret-value"

        rendered = f"{report.header_keys}{[s.detail for s in report.signals]}"
        assert "super-secret-value" not in rendered


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
    """It has to be safe to run beside a live process; hijacking the global provider is not."""
    from opentelemetry import trace

    before = trace.get_tracer_provider()
    with _CollectorStub(status=200) as collector:
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", collector.endpoint)
        run_doctor(timeout=5)

    assert trace.get_tracer_provider() is before

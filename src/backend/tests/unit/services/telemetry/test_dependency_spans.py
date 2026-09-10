"""Dependency spans and sampling.

Database spans are allowlisted for export; the LLM vendor transports deliberately are not.
Sampling needs no code of ours, so the check here is that it stays that way.

Each case runs in a subprocess because the tracer provider is process-global.
"""

import gzip
import http.server
import json
import os
import subprocess
import sys
import threading

import pytest
from lfx.observability import APPLICATION_INSTRUMENTATION_SCOPES


class _Collector(http.server.BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        if self.headers.get("Content-Encoding") == "gzip":
            body = gzip.decompress(body)
        self.server.requests.append((self.path, body))
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *args) -> None:
        pass


@pytest.fixture
def collector():
    server = http.server.HTTPServer(("127.0.0.1", 0), _Collector)
    server.requests = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def test_outbound_http_scopes_stay_out_of_the_allowlist():
    """Redacting URLs does not make the LLM transports safe to export; that boundary stands."""
    for scope in (
        "opentelemetry.instrumentation.httpx",
        "opentelemetry.instrumentation.requests",
        "opentelemetry.instrumentation.urllib3",
    ):
        assert scope not in APPLICATION_INSTRUMENTATION_SCOPES


def test_database_spans_are_allowlisted():
    """The scope is on the list. What it carries is the next test, which is the part that matters."""
    assert "opentelemetry.instrumentation.sqlalchemy" in APPLICATION_INSTRUMENTATION_SCOPES


# Admitting the SQLAlchemy scope rests on one claim: db.statement keeps bound parameters as
# placeholders, so row values stay in the database. That claim is why chat message text is
# considered safe from this signal, and it was carried by a comment and a membership check
# rather than by running a query. This runs the query.
#
# The membership check alone passes in every way this can actually break: the instrumentor not
# installed, instrument() raising and being swallowed, or a future version rendering literals
# into the statement.
DB_SENTINEL = "SENTINEL-chat-row-value-QQQ"

DB_SPAN_PROBE = f"""
import json, sys

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from sqlalchemy import create_engine, text

from lfx.observability import ApplicationOnlySpanProcessor, instrument_database

exporter = InMemorySpanExporter()
provider = TracerProvider()
provider.add_span_processor(ApplicationOnlySpanProcessor(exporter))
trace.set_tracer_provider(provider)

SENTINEL = {DB_SENTINEL!r}
literal = len(sys.argv) > 1 and sys.argv[1] == "literal"

engine = create_engine("sqlite+pysqlite:///:memory:")
instrument_database(engine)

with engine.connect() as connection:
    connection.execute(text("CREATE TABLE messagetable (text VARCHAR)"))
    if literal:
        # What a regression to literal rendering would look like. Never how the runtime writes.
        connection.execute(text("INSERT INTO messagetable (text) VALUES ('" + SENTINEL + "')"))
    else:
        # A bound parameter, the shape the runtime uses to store a chat message.
        connection.execute(text("INSERT INTO messagetable (text) VALUES (:text)"), {{"text": SENTINEL}})
    connection.commit()

provider.force_flush()
spans = [
    {{
        "name": s.name,
        "scope": s.instrumentation_scope.name if s.instrumentation_scope else None,
        "attrs": {{k: str(v) for k, v in (s.attributes or {{}}).items()}},
    }}
    for s in exporter.get_finished_spans()
]
print("PROBE_RESULT " + json.dumps({{"spans": spans}}))
"""  # noqa: S608 - the interpolated INSERT is the control, not a query we run


def _run_db_probe(*args: str) -> list[dict]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("OTEL_")}
    completed = subprocess.run(  # noqa: S603
        [sys.executable, "-c", DB_SPAN_PROBE, *args],
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    # Not next(): a probe that exits cleanly without printing would raise StopIteration here and
    # take its own stdout and stderr with it, which is the context needed to see why.
    lines = [ln for ln in completed.stdout.splitlines() if ln.startswith("PROBE_RESULT ")]
    assert lines, f"probe printed no result.\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
    spans = json.loads(lines[0].removeprefix("PROBE_RESULT "))["spans"]
    return [s for s in spans if s["scope"] == "opentelemetry.instrumentation.sqlalchemy"]


def test_a_database_span_carries_the_placeholder_and_not_the_row_value():
    """The claim that admits this scope, run rather than asserted.

    A chat message is stored through a bound parameter, so if the instrumentation rendered
    values into ``db.statement`` the conversation would reach the operator's APM on a scope we
    allowlisted on the strength of it not doing that.
    """
    db_spans = _run_db_probe()

    # Not a formality: without it this passes when the instrumentor is missing entirely.
    assert db_spans, "no sqlalchemy spans were exported"

    statements = [s["attrs"].get("db.statement", "") for s in db_spans]
    # The placeholder, not just the verb: a statement truncated to "INSERT INTO messagetable"
    # would satisfy a looser check and satisfy the sentinel check for the wrong reason.
    assert any("INSERT INTO messagetable (text) VALUES (?)" in statement for statement in statements), statements
    assert DB_SENTINEL not in json.dumps(db_spans), f"a bound row value reached the APM: {db_spans}"


def test_the_probe_would_have_seen_a_row_value_in_the_statement():
    """The control, because every assertion above is an absence and an absence proves nothing.

    Same probe, same exporter, the value interpolated into the SQL instead of bound.
    """
    db_spans = _run_db_probe("literal")

    assert db_spans
    assert DB_SENTINEL in json.dumps(db_spans), "the probe cannot see a value in db.statement at all"


# The ticket's sampler criterion, run against the real bootstrap rather than a hand-built
# provider: the same request at ratio 0.0 must export nothing and at 1.0 must export the lot.
SAMPLER_PROBE = """
import json
from opentelemetry import trace
from lfx.observability import APPLICATION_TRACER_NAME, bootstrap_application_telemetry

telemetry = bootstrap_application_telemetry()
tracer = trace.get_tracer(APPLICATION_TRACER_NAME)
for _ in range(20):
    with tracer.start_as_current_span("flow.execute"):
        pass
telemetry.shutdown()
print("PROBE_RESULT done")
"""


def _run_sampler_probe(endpoint: str, ratio: str) -> None:
    env = {k: v for k, v in os.environ.items() if not k.startswith("OTEL_")}
    env["OTEL_EXPORTER_OTLP_ENDPOINT"] = endpoint
    env["OTEL_EXPORTER_OTLP_PROTOCOL"] = "http/protobuf"
    env["OTEL_TRACES_SAMPLER"] = "traceidratio"
    env["OTEL_TRACES_SAMPLER_ARG"] = ratio
    completed = subprocess.run(  # noqa: S603
        [sys.executable, "-c", SAMPLER_PROBE],
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr


def _exported_span_count(requests_seen) -> int:
    from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest

    total = 0
    for path, body in requests_seen:
        if path != "/v1/traces":
            continue
        request = ExportTraceServiceRequest()
        request.ParseFromString(body)
        for rs in request.resource_spans:
            for ss in rs.scope_spans:
                total += len(ss.spans)
    return total


def test_sampling_off_exports_nothing(collector):
    port = collector.server_address[1]
    _run_sampler_probe(f"http://127.0.0.1:{port}", "0.0")

    assert _exported_span_count(collector.requests) == 0


def test_sampling_on_exports_every_span(collector):
    port = collector.server_address[1]
    _run_sampler_probe(f"http://127.0.0.1:{port}", "1.0")

    assert _exported_span_count(collector.requests) == 20

"""A SQLite database path must not leave the process as a span name.

SQLAlchemy's instrumentation sets ``db.name`` from the database name, and for SQLite that name
is the file path. It builds ``db.operation`` and the span name as ``"<operation> <db.name>"``,
so without this the operator's APM shows spans named
``SELECT /home/alice/langflow/langflow.db``. SQLite is the default database, so that is the
default configuration rather than an edge case.

The file name is kept rather than dropped, because someone running more than one SQLite
database still has to tell them apart.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

pytest.importorskip("opentelemetry.sdk.trace.export.in_memory_span_exporter")

from lfx.observability import ApplicationOnlySpanProcessor, _shorten_db_path

# A directory that gives away the account name, which is the part of a real path worth not
# sending. The file name is the part that survives.
DB_PATH = "/home/alice/deployments/langflow-prod/langflow.db"
DB_FILE = "langflow.db"


def export(name: str, attributes: dict):
    """Push one span through the processor and return it as the exporter received it."""
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(ApplicationOnlySpanProcessor(exporter))
    try:
        span = provider.get_tracer("opentelemetry.instrumentation.sqlalchemy").start_span(name)
        for key, value in attributes.items():
            span.set_attribute(key, value)
        span.end()
        provider.force_flush()
        finished = exporter.get_finished_spans()
        assert len(finished) == 1, finished
        return finished[0]
    finally:
        provider.shutdown()


def test_the_span_name_carries_the_file_name_not_the_path():
    span = export(
        f"SELECT {DB_PATH}",
        {"db.system": "sqlite", "db.name": DB_PATH, "db.operation": f"SELECT {DB_PATH}"},
    )

    assert span.name == f"SELECT {DB_FILE}"
    assert span.attributes["db.name"] == DB_FILE
    assert span.attributes["db.operation"] == f"SELECT {DB_FILE}"


def test_no_part_of_the_directory_survives_anywhere_on_the_span():
    """Serialise the whole span, because the path could hide on an attribute not asserted above."""
    span = export(
        f"SELECT {DB_PATH}",
        {"db.system": "sqlite", "db.name": DB_PATH, "db.operation": f"SELECT {DB_PATH}"},
    )
    dumped = json.dumps({"name": span.name, "attributes": dict(span.attributes)})

    assert "alice" not in dumped, dumped
    assert "/home" not in dumped, dumped
    assert DB_FILE in dumped, "the file name should survive; only the directory is dropped"


def test_other_attributes_are_untouched():
    span = export(
        f"SELECT {DB_PATH}",
        {
            "db.system": "sqlite",
            "db.name": DB_PATH,
            "db.operation": f"SELECT {DB_PATH}",
            "db.statement": "SELECT flow.name FROM flow WHERE flow.id = ?",
        },
    )

    assert span.attributes["db.system"] == "sqlite"
    assert span.attributes["db.statement"] == "SELECT flow.name FROM flow WHERE flow.id = ?"


def test_a_postgres_name_containing_a_separator_is_left_alone():
    """The gate is db.system, not the shape of the value.

    A separator is legal inside a Postgres database name. Shortening one would silently
    rename a logical database in the operator's dashboards, which is a worse bug than the
    leak this function exists to fix.
    """
    span = export(
        "SELECT tenant/archive",
        {"db.system": "postgresql", "db.name": "tenant/archive", "db.operation": "SELECT tenant/archive"},
    )

    assert span.name == "SELECT tenant/archive"
    assert span.attributes["db.name"] == "tenant/archive"


def test_a_path_without_a_sqlite_system_is_left_alone():
    """No db.system means no evidence it is a file, so nothing is assumed."""
    span = export(f"SELECT {DB_PATH}", {"db.name": DB_PATH})

    assert span.attributes["db.name"] == DB_PATH


def test_a_logical_database_name_is_left_alone():
    """Postgres and MySQL report a name with no separator, so nothing should change."""
    span = export(
        "SELECT langflow", {"db.system": "postgresql", "db.name": "langflow", "db.operation": "SELECT langflow"}
    )

    assert span.name == "SELECT langflow"
    assert span.attributes["db.name"] == "langflow"


def test_a_windows_path_is_shortened_too():
    """The exporting host and the host that wrote the path need not be the same platform."""
    windows_path = r"C:\\Users\\alice\\langflow\\langflow.db"
    span = export(f"SELECT {windows_path}", {"db.system": "sqlite", "db.name": windows_path})

    assert span.attributes["db.name"] == DB_FILE
    assert "alice" not in span.name, span.name


def test_a_span_with_no_db_name_is_unchanged():
    span = export("flow.execute", {"flow_id": "abc", "status": "ok"})

    assert span.name == "flow.execute"
    assert span.attributes["flow_id"] == "abc"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("/a/b/c.db", "c.db"),
        ("c.db", "c.db"),
        ("langflow", "langflow"),
        (":memory:", ":memory:"),
        ("", ""),
        ("/", ""),
        ("relative/path/x.db", "x.db"),
    ],
)
def test_shorten_db_path(value, expected):
    assert _shorten_db_path(value) == expected


# The end-to-end half. A real SQLite engine and the real instrumentor, in a subprocess because
# SQLAlchemyInstrumentor patches globally and the tracer provider is process-wide.

PROBE = """
import json, os, tempfile

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from lfx.observability import ApplicationOnlySpanProcessor, instrument_database

exporter = InMemorySpanExporter()
provider = TracerProvider()
provider.add_span_processor(ApplicationOnlySpanProcessor(exporter))
trace.set_tracer_provider(provider)

import sqlalchemy as sa

# A real file, in a directory whose name is the thing that must not be exported.
root = tempfile.mkdtemp(prefix="SENTINELDIRQQQ-")
db_file = os.path.join(root, "langflow.db")
engine = sa.create_engine("sqlite:///" + db_file)
instrument_database(engine)

with engine.connect() as conn:
    conn.execute(sa.text("SELECT 1"))

provider.force_flush()
spans = [
    {"name": s.name, "attributes": {k: str(v) for k, v in (s.attributes or {}).items()}}
    for s in exporter.get_finished_spans()
]
print("PROBE_RESULT " + json.dumps({"root": root, "db_file": db_file, "spans": spans}))
"""


def run_probe() -> dict:
    import os

    env = {k: v for k, v in os.environ.items() if not k.startswith("OTEL_")}
    with tempfile.TemporaryDirectory() as tmp:
        probe = Path(tmp) / "probe.py"
        probe.write_text(PROBE, encoding="utf-8")
        completed = subprocess.run(  # noqa: S603
            [sys.executable, str(probe)], env=env, capture_output=True, text=True, timeout=300, check=False
        )
    assert completed.returncode == 0, completed.stderr
    lines = [ln for ln in completed.stdout.splitlines() if ln.startswith("PROBE_RESULT ")]
    assert lines, f"probe printed no result.\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
    return json.loads(lines[0].removeprefix("PROBE_RESULT "))


def test_a_real_query_exports_no_host_path():
    """The regression this file exists for, against the real instrumentor rather than a stub."""
    result = run_probe()
    dumped = json.dumps(result["spans"])

    # Asserted before the absence: if the probe produced no database spans at all, "the path is
    # not here" would pass while proving nothing.
    assert any(s["attributes"].get("db.system") == "sqlite" for s in result["spans"]), result

    assert "SENTINELDIRQQQ" not in dumped, dumped
    assert result["root"] not in dumped, dumped
    assert "langflow.db" in dumped, "the file name should survive"

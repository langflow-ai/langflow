"""DB spans must carry what span metrics group by: the phase, the component, the table and verb.

Span metrics are computed per span and know nothing about parents. A DB span named
``SELECT langflow`` therefore cannot be split into work before, inside or after a flow run, or
by table, unless it carries those as attributes of its own.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

pytest.importorskip("opentelemetry.sdk.trace.export.in_memory_span_exporter")

from lfx import observability as otel


def export(attributes: dict, *, name: str = "SELECT langflow", lent: dict | None = None):
    """Start and end one DB span through the processor, optionally inside a lent phase."""
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(otel.ApplicationOnlySpanProcessor(exporter))
    try:
        with otel.db_attribution(lent):
            span = provider.get_tracer(otel.DB_INSTRUMENTATION_SCOPE).start_span(name)
        # Like the instrumentor, the statement is set after the span starts.
        for key, value in attributes.items():
            span.set_attribute(key, value)
        span.end()
        provider.force_flush()
        (finished,) = exporter.get_finished_spans()
        return finished
    finally:
        provider.shutdown()


@pytest.mark.parametrize(
    ("statement", "operation", "table"),
    [
        (
            "SELECT message.id, message.text, message.sender_from FROM message WHERE message.session_id = ?",
            "SELECT",
            "message",
        ),
        ("INSERT INTO message (id, text) VALUES (?, ?)", "INSERT", "message"),
        ("UPDATE job SET status=$1::VARCHAR WHERE job.job_id = $2::UUID", "UPDATE", "job"),
        ("DELETE FROM vertex_build WHERE vertex_build.flow_id = $1", "DELETE", "vertex_build"),
        ('SELECT "user".id FROM "user" WHERE "user".id = $1', "SELECT", "user"),
        ("select apikey.id from public.apikey where apikey.api_key = $1", "SELECT", "apikey"),
        ("SELECT count(*) AS count_1 FROM (SELECT flow.id AS id FROM flow) AS anon_1", "SELECT", "flow"),
        ("  SELECT 1", "SELECT", None),
        ("BEGIN", "BEGIN", None),
    ],
)
def test_the_verb_and_first_table_are_recorded(statement, operation, table):
    span = export({"db.system": "postgresql", "db.statement": statement})

    assert span.attributes["db.operation.name"] == operation
    assert span.attributes.get("db.collection.name") == table
    assert span.attributes["db.statement"] == statement
    # Semantic-convention name: the verb and table, or the verb alone, never the database name.
    assert span.name == (f"{operation} {table}" if table else operation)


def test_the_stable_semconv_statement_is_read_and_its_operation_corrected():
    """The instrumentor's stable mode writes "<verb> <db.name>" as db.operation.name."""
    span = export({"db.query.text": "INSERT INTO job (id) VALUES ($1)", "db.operation.name": "INSERT langflow"})

    assert span.attributes["db.operation.name"] == "INSERT"
    assert span.attributes["db.collection.name"] == "job"


@pytest.mark.parametrize(
    "statement",
    ["PRAGMA table_info(flow)", "EXPLAIN SELECT 1 FROM flow", "", "123"],
)
def test_an_unlisted_verb_records_nothing(statement):
    span = export({"db.statement": statement})

    assert "db.operation.name" not in span.attributes
    assert "db.collection.name" not in span.attributes
    assert span.name == "SELECT langflow"


def test_a_sqlite_statement_span_is_named_by_table_not_file():
    span = export(
        {"db.system": "sqlite", "db.name": "/home/alice/langflow.db", "db.statement": "SELECT flow.id FROM flow"},
        name="SELECT /home/alice/langflow.db",
    )

    assert span.name == "SELECT flow"
    assert span.attributes["db.name"] == "langflow.db"


def test_a_table_past_the_scan_limit_is_not_recorded():
    columns = ", ".join(f"message.column_{i}" for i in range(1000))
    span = export({"db.statement": f"SELECT {columns} FROM message"})  # noqa: S608 - never executed

    assert span.attributes["db.operation.name"] == "SELECT"
    assert "db.collection.name" not in span.attributes


def test_a_db_span_takes_the_enclosing_phase_and_component():
    lent = {"langflow.phase": "vertex.execute", "langflow.component.type": "ChatOutput"}
    span = export({"db.statement": "INSERT INTO message (id) VALUES (?)"}, lent=lent)

    assert span.attributes["langflow.phase"] == "vertex.execute"
    assert span.attributes["langflow.component.type"] == "ChatOutput"


def test_a_connect_span_takes_the_phase_but_records_no_statement_attributes():
    span = export({"db.system": "postgresql"}, name="connect", lent={"langflow.phase": "job.status"})

    assert span.attributes["langflow.phase"] == "job.status"
    assert "db.operation.name" not in span.attributes
    assert span.name == "connect"


def test_outside_any_phase_nothing_is_invented():
    span = export({"db.statement": "SELECT flow.id FROM flow"})

    assert "langflow.phase" not in span.attributes
    assert span.attributes["db.collection.name"] == "flow"


def test_only_db_spans_borrow_the_phase():
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(otel.ApplicationOnlySpanProcessor(exporter))
    with otel.db_attribution({"langflow.phase": "job.status"}):
        provider.get_tracer("opentelemetry.instrumentation.fastapi").start_span("GET /x").end()
    provider.force_flush()
    (span,) = exporter.get_finished_spans()
    provider.shutdown()

    assert "langflow.phase" not in span.attributes


def test_a_scope_without_a_phase_keeps_the_enclosing_one():
    with otel.db_attribution({"langflow.phase": "job.execute"}):
        with otel.db_attribution({"protocol": "v2"}) as lent:
            assert lent is None
            assert otel._current_db_attribution.get() == {"langflow.phase": "job.execute"}
        with otel.db_attribution({"langflow.phase": "vertex.execute", "flow_id": "not lent"}):
            assert otel._current_db_attribution.get() == {"langflow.phase": "vertex.execute"}
        assert otel._current_db_attribution.get() == {"langflow.phase": "job.execute"}
    assert otel._current_db_attribution.get() is None


# The end-to-end half: a real async engine and the real instrumentor, in a subprocess because
# SQLAlchemyInstrumentor patches globally and the tracer provider is process-wide. This is the
# part a stub cannot prove: that the phase survives SQLAlchemy's greenlet bridge from the
# awaiting coroutine to the sync cursor call where the span starts.

PROBE = """
import asyncio, json

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from lfx.observability import ApplicationOnlySpanProcessor, instrument_database

exporter = InMemorySpanExporter()
provider = TracerProvider()
provider.add_span_processor(ApplicationOnlySpanProcessor(exporter))
trace.set_tracer_provider(provider)

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

from lfx.application_observability import db_phase, observe_db_phase


@observe_db_phase("job.create")
async def create(conn):
    await conn.execute(sa.text("INSERT INTO job (id) VALUES (1)"))


async def main():
    engine = create_async_engine("sqlite+aiosqlite://")
    instrument_database(engine)
    async with engine.connect() as conn:
        await conn.execute(sa.text("CREATE TABLE job (id INTEGER)"))
        await create(conn)
        with db_phase("job.finish"):
            await conn.execute(sa.text("UPDATE job SET id = 2"))
    await engine.dispose()


asyncio.run(main())
provider.force_flush()
spans = [
    {"name": s.name, "attributes": {k: str(v) for k, v in (s.attributes or {}).items()}}
    for s in exporter.get_finished_spans()
]
print("PROBE_RESULT " + json.dumps(spans))
"""


def test_a_real_async_query_carries_its_phase_table_and_verb():
    pytest.importorskip("aiosqlite")
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
    spans = json.loads(lines[0].removeprefix("PROBE_RESULT "))
    by_verb = {s["attributes"].get("db.operation.name"): s["attributes"] for s in spans}
    names = {s["name"] for s in spans}
    assert {"INSERT job", "UPDATE job", "connect"} <= names, names

    assert by_verb["INSERT"]["langflow.phase"] == "job.create"
    assert by_verb["INSERT"]["db.collection.name"] == "job"
    assert by_verb["UPDATE"]["langflow.phase"] == "job.finish"
    # CREATE is not a listed verb, and it ran outside any phase: nothing is invented for it.
    assert "langflow.phase" not in by_verb[None]

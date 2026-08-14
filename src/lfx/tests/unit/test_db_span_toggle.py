"""Database spans are the bulk of the export, so an operator can turn them off.

Measured against a live run: database spans were about 80% of everything exported, roughly
50 spans per flow run against a single ``flow.execute``. A commercial APM bills per span
ingested, so an operator who only wants flow and request health should not have to pay for
the rest of it.

They stay on by default because the volume buys something. In that same run 17% of pool
checkouts took over 50ms and 4% took over 200ms, which is the difference between knowing a
flow was slow and knowing it was slow waiting for the database.

The property that matters most here is not the toggle. It is that the toggle can only ever
*subtract* from the allowlist, because the allowlist is what keeps prompt-carrying scopes out
of the APM. Configuration that could widen it would be an env var that reopens the leak.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

pytest.importorskip("opentelemetry.sdk.trace.export.in_memory_span_exporter")

from lfx.observability import (
    APPLICATION_INSTRUMENTATION_SCOPES,
    APPLICATION_TRACER_NAME,
    DB_INSTRUMENTATION_SCOPE,
    ApplicationOnlySpanProcessor,
    db_spans_enabled,
    exported_span_scopes,
)

ENV_VAR = "LANGFLOW_OTEL_DB_SPANS"


def exported_names(env_value: str | None, scopes: list[str], monkeypatch) -> list[str]:
    """Emit one span per scope through a freshly built processor, return what got exported.

    The processor resolves its scope set at construction, so the environment has to be set
    before it is built. Building it inside the helper rather than in a fixture is what makes
    that ordering explicit.
    """
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    if env_value is None:
        monkeypatch.delenv(ENV_VAR, raising=False)
    else:
        monkeypatch.setenv(ENV_VAR, env_value)

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(ApplicationOnlySpanProcessor(exporter))
    try:
        for scope in scopes:
            provider.get_tracer(scope).start_span(f"span-from-{scope}").end()
        provider.force_flush()
        return [s.name for s in exporter.get_finished_spans()]
    finally:
        provider.shutdown()


def test_database_spans_are_exported_by_default(monkeypatch):
    """The default, asserted before any of the absences below mean anything."""
    exported = exported_names(None, [DB_INSTRUMENTATION_SCOPE], monkeypatch)

    assert exported == [f"span-from-{DB_INSTRUMENTATION_SCOPE}"]


@pytest.mark.parametrize("off", ["false", "0", "no", "off", "FALSE", "Off", " false "])
def test_database_spans_are_dropped_when_turned_off(off, monkeypatch):
    """Paired with the flow span, which must still export.

    Without that second scope in the same run, an empty list reads the same whether the
    toggle worked or the processor stopped exporting anything at all.
    """
    exported = exported_names(off, [DB_INSTRUMENTATION_SCOPE, APPLICATION_TRACER_NAME], monkeypatch)

    assert exported == [f"span-from-{APPLICATION_TRACER_NAME}"]


@pytest.mark.parametrize("value", ["true", "1", "yes", "on", "", "maybe", "flase", "off ish", "2"])
def test_only_a_recognised_false_value_turns_them_off(value, monkeypatch):
    """A typo must not silently stop telemetry the operator believes is running.

    ``flase`` is in the list on purpose. It is the plausible typo, and the failure it would
    cause is invisible: telemetry quietly stops and nothing says so.
    """
    exported = exported_names(value, [DB_INSTRUMENTATION_SCOPE], monkeypatch)

    assert exported == [f"span-from-{DB_INSTRUMENTATION_SCOPE}"]


@pytest.mark.parametrize(
    "value",
    ["true", "false", "0", "1", "", "garbage", "opentelemetry.instrumentation.openai", "*", "all"],
)
def test_configuration_can_only_subtract_from_the_allowlist(value, monkeypatch):
    """The safety property. No env value may widen the boundary.

    Includes a value naming an LLM scope and a couple of wildcard-looking strings, because
    the failure worth guarding against is a future parser that treats the variable as a list
    of scopes to admit rather than as a boolean.
    """
    monkeypatch.setenv(ENV_VAR, value)

    assert exported_span_scopes() <= APPLICATION_INSTRUMENTATION_SCOPES


def test_turning_them_off_removes_exactly_the_database_scope(monkeypatch):
    monkeypatch.setenv(ENV_VAR, "false")

    assert APPLICATION_INSTRUMENTATION_SCOPES - exported_span_scopes() == {DB_INSTRUMENTATION_SCOPE}


def test_db_spans_enabled_reflects_the_variable(monkeypatch):
    monkeypatch.delenv(ENV_VAR, raising=False)
    assert db_spans_enabled() is True
    monkeypatch.setenv(ENV_VAR, "false")
    assert db_spans_enabled() is False


# The end-to-end half. A real sqlite engine and the real instrumentor, in a subprocess because
# SQLAlchemyInstrumentor patches globally and the tracer provider is process-wide, so an
# in-process version of this would leak state into whatever test ran next.

PROBE = """
import json, sys

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from lfx.observability import ApplicationOnlySpanProcessor, instrument_database

exporter = InMemorySpanExporter()
provider = TracerProvider()
provider.add_span_processor(ApplicationOnlySpanProcessor(exporter))
trace.set_tracer_provider(provider)

import sqlalchemy as sa

engine = sa.create_engine("sqlite://")
instrument_database(engine)

with engine.connect() as conn:
    conn.execute(sa.text("SELECT 1"))

# A flow span too, so "nothing exported" and "db spans suppressed" cannot be confused.
provider.get_tracer("langflow.observability").start_span("flow.execute").end()

provider.force_flush()
names = [s.name for s in exporter.get_finished_spans()]
scopes = [s.instrumentation_scope.name if s.instrumentation_scope else "" for s in exporter.get_finished_spans()]
print("PROBE_RESULT " + json.dumps({"names": names, "scopes": scopes}))
"""


def run_probe(env_value: str | None) -> dict:
    import os

    env = {k: v for k, v in os.environ.items() if not k.startswith("OTEL_")}
    env.pop(ENV_VAR, None)
    if env_value is not None:
        env[ENV_VAR] = env_value
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


def test_a_real_query_produces_database_spans_by_default():
    """The positive control for the test below, run against the real instrumentor."""
    result = run_probe(None)

    assert DB_INSTRUMENTATION_SCOPE in result["scopes"], result
    assert "flow.execute" in result["names"], result


def test_a_real_query_produces_no_database_spans_when_turned_off():
    """And the flow span still exports, so the probe is demonstrably still looking."""
    result = run_probe("false")

    assert DB_INSTRUMENTATION_SCOPE not in result["scopes"], result
    assert "flow.execute" in result["names"], result


# Proving the instrumentor never attached, rather than that its spans were filtered out.
# The distinction is the whole point of the two gates: the export filter alone would still
# pay the cost of creating every span. This probe deliberately uses a plain
# SimpleSpanProcessor with no filtering, so a span that exists at all is visible.

UNFILTERED_PROBE = """
import json

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from lfx.observability import instrument_database

exporter = InMemorySpanExporter()
provider = TracerProvider()
# No ApplicationOnlySpanProcessor here on purpose: nothing is filtered, so any span the
# sqlalchemy instrumentor creates will show up.
provider.add_span_processor(SimpleSpanProcessor(exporter))
trace.set_tracer_provider(provider)

import sqlalchemy as sa

engine = sa.create_engine("sqlite://")
instrument_database(engine)

with engine.connect() as conn:
    conn.execute(sa.text("SELECT 1"))

provider.force_flush()
scopes = [s.instrumentation_scope.name if s.instrumentation_scope else "" for s in exporter.get_finished_spans()]
print("PROBE_RESULT " + json.dumps({"scopes": scopes}))
"""


def run_unfiltered_probe(env_value: str | None) -> dict:
    import os

    env = {k: v for k, v in os.environ.items() if not k.startswith("OTEL_")}
    env.pop(ENV_VAR, None)
    if env_value is not None:
        env[ENV_VAR] = env_value
    with tempfile.TemporaryDirectory() as tmp:
        probe = Path(tmp) / "probe.py"
        probe.write_text(UNFILTERED_PROBE, encoding="utf-8")
        completed = subprocess.run(  # noqa: S603
            [sys.executable, str(probe)], env=env, capture_output=True, text=True, timeout=300, check=False
        )
    assert completed.returncode == 0, completed.stderr
    lines = [ln for ln in completed.stdout.splitlines() if ln.startswith("PROBE_RESULT ")]
    assert lines, f"probe printed no result.\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
    return json.loads(lines[0].removeprefix("PROBE_RESULT "))


def test_the_instrumentor_attaches_by_default():
    """The control: with no filtering in the way, a query does produce database spans."""
    result = run_unfiltered_probe(None)

    assert DB_INSTRUMENTATION_SCOPE in result["scopes"], result


def test_the_instrumentor_is_not_attached_when_turned_off():
    """Skipped, not filtered.

    Nothing filters in this probe, so a database span here would mean the instrumentor had
    attached and the export boundary was doing the suppressing. The span-creation cost would
    still be paid on every query, which is half of what turning this off is meant to save.
    """
    result = run_unfiltered_probe("false")

    assert DB_INSTRUMENTATION_SCOPE not in result["scopes"], result

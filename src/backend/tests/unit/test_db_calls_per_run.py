"""Count the database work one flow run costs on the request-handling connection pool.

Measures with SQLAlchemy's own ``before_cursor_execute`` and pool ``checkout`` events rather than
with OpenTelemetry spans. The events are the same source the instrumentor wraps, they need no
exporter, and they report the statement text directly, so a regression names the table it came
from instead of a span count.

The listeners attach to the request pool engine only. That is deliberate: the telemetry writer
owns a dedicated engine, so ``transaction`` and ``vertex_build`` rows are correctly invisible here.
What this file measures is the work a caller waits on.

Two autouse fixtures in ``tests/conftest.py`` move the suite off the production configuration:
``disable_telemetry_writer`` forces the legacy synchronous write path, and ``deactivate_tracing``
switches the internal trace/span tables off. Both are overridden below, because a per-run cost
measured under test-only settings is not the cost users pay.

Run it as a report::

    uv run pytest src/backend/tests/unit/test_db_calls_per_run.py -s

``-s`` matters: the per-table ledger goes to stdout, and that ledger is the deliverable. The
asserted budgets are ceilings, set from a measured baseline, not targets.
"""

import re
from collections import Counter
from dataclasses import dataclass, field

import pytest
from sqlalchemy import event
from starlette import status

# Ceilings, not targets. A two-component flow measured 13 statements and 11 checkouts on SQLite
# when these were set, down from 27 and 11. The headroom absorbs an extra message or span without
# failing; anything past it means a new query joined the request path and should be justified.
#
# The floor for this flow is 10, counted from what a run cannot skip: read the api key (1), read the
# flow (1), read the global variables (1), check memory-base (1), insert the job row (1), write its
# terminal status (1), write the two messages (2), write the trace and its spans (2).
#
# The three above that floor are the `UPDATE job` to in_progress, the pre-update `SELECT message`,
# and the `UPDATE apikey` usage counter. Each is removable and none is removed here.
STATEMENT_BUDGET = 16
CHECKOUT_BUDGET = 12

# A run rejected before execution measured 4 statements and 3 checkouts: the api key read and its
# usage write, the flow read, and the global-variable read. It reaches none of the run's own work.
REJECTED_RUN_BUDGET = 6
REJECTED_RUN_CHECKOUT_BUDGET = 4


@pytest.fixture
def production_telemetry_defaults(monkeypatch):
    """Undo the two autouse fixtures that take the suite off the shipped configuration.

    Must be requested before ``client``: both settings are read while the app starts up.
    """
    monkeypatch.setenv("LANGFLOW_TELEMETRY_WRITER_ENABLED", "true")
    monkeypatch.setenv("LANGFLOW_DEACTIVATE_TRACING", "false")
    yield
    monkeypatch.undo()


_OP = re.compile(r"^\s*(SELECT|INSERT|UPDATE|DELETE|BEGIN|COMMIT|ROLLBACK|PRAGMA|SAVEPOINT|RELEASE)", re.IGNORECASE)
_TABLE = re.compile(r"\b(?:FROM|INTO|UPDATE|JOIN)\s+[\"'`\[]?(\w+)", re.IGNORECASE)


def _classify(sql: str) -> tuple[str, str]:
    """Reduce a statement to (operation, table). Unparsed statements keep their first word."""
    op_match = _OP.match(sql)
    op = op_match.group(1).upper() if op_match else sql.split(maxsplit=1)[0].upper()
    table_match = _TABLE.search(sql)
    return op, table_match.group(1).lower() if table_match else "-"


@dataclass
class DbLedger:
    """Every statement and pool checkout seen while the recorder was attached."""

    statements: list[str] = field(default_factory=list)
    checkouts: int = 0

    @property
    def by_op_table(self) -> Counter:
        return Counter(_classify(sql) for sql in self.statements)

    @property
    def writes(self) -> int:
        return sum(1 for sql in self.statements if _classify(sql)[0] in {"INSERT", "UPDATE", "DELETE"})

    def report(self, title: str) -> str:
        lines = [
            "",
            f"=== {title} ===",
            f"statements: {len(self.statements)}   writes: {self.writes}   pool checkouts: {self.checkouts}",
            "",
        ]
        lines.extend(
            f"  {count:>4}  {op:<9} {table}"
            for (op, table), count in sorted(self.by_op_table.items(), key=lambda kv: -kv[1])
        )
        return "\n".join(lines)


@pytest.fixture
async def db_ledger():
    """Record statements and pool checkouts on the live engine for the duration of a test."""
    from langflow.services.deps import get_db_service

    engine = get_db_service().engine
    sync_engine = engine.sync_engine
    ledger = DbLedger()

    def on_execute(_conn, _cursor, statement, _params, _context, _executemany):
        ledger.statements.append(statement)

    def on_checkout(_dbapi_conn, _record, _proxy):
        ledger.checkouts += 1

    event.listen(sync_engine, "before_cursor_execute", on_execute)
    event.listen(sync_engine.pool, "checkout", on_checkout)
    try:
        yield ledger
    finally:
        event.remove(sync_engine, "before_cursor_execute", on_execute)
        event.remove(sync_engine.pool, "checkout", on_checkout)


async def test_db_calls_for_a_healthy_run(
    production_telemetry_defaults,  # noqa: ARG001 - fixture must apply before `client` builds the app
    client,
    simple_api_test,
    created_api_key,
    db_ledger,
):
    """A successful run stays inside its statement and checkout budget."""
    headers = {"x-api-key": created_api_key.api_key}
    flow_id = simple_api_test["id"]

    # The first request of a process warms caches that are not per-run work. Measure the second.
    warmup = await client.post(f"/api/v1/run/{flow_id}", headers=headers, json={"output_type": "text"})
    assert warmup.status_code == status.HTTP_200_OK, warmup.text

    db_ledger.statements.clear()
    db_ledger.checkouts = 0

    response = await client.post(f"/api/v1/run/{flow_id}", headers=headers, json={"output_type": "text"})
    assert response.status_code == status.HTTP_200_OK, response.text

    print(db_ledger.report("healthy run"))  # noqa: T201 - the ledger is the deliverable

    # The totals are a backstop. They are ceilings with headroom, so a single query coming back
    # would slip under them; these name the specific reads that were removed, so each one is
    # defended on its own. They are also immune to the trace flush occasionally settling after the
    # response, which moves the totals but not these counts.
    counts = db_ledger.by_op_table
    assert counts[("SELECT", "user")] == 0, "the owning user rides along on the api key lookup"
    assert counts[("SELECT", "job")] == 0, "update_job_status must not re-read the row it wrote"
    assert counts[("SELECT", "message")] <= 1, "the post-commit message refresh must not come back"
    assert counts[("INSERT", "span")] <= 1, "spans are written in one statement, not one per span"
    assert counts[("SELECT", "span")] == 0, "spans are inserted without a merge() primary-key probe"

    assert len(db_ledger.statements) <= STATEMENT_BUDGET, db_ledger.report("over statement budget")
    assert db_ledger.checkouts <= CHECKOUT_BUDGET, db_ledger.report("over checkout budget")


async def test_db_calls_for_a_failing_run(
    production_telemetry_defaults,  # noqa: ARG001 - fixture must apply before `client` builds the app
    client,
    simple_api_test,
    created_api_key,
    db_ledger,
):
    """A rejected run must not cost more database work than one that succeeds.

    Blocking a component the flow uses rejects the run after authentication and after the flow
    load, so this covers the setup work a 404 or a 401 would skip. It stops there, though: the
    run never reaches the job, message or trace writes, so this does NOT cover the failure mode
    that motivated the check, which is a run that does all of that work and then fails partway
    through. Covering that needs a component that raises mid-execution, and is still open.
    """
    from lfx.services.deps import get_catalog_policy_service

    headers = {"x-api-key": created_api_key.api_key}
    flow_id = simple_api_test["id"]
    catalog_policy_service = get_catalog_policy_service()

    warmup = await client.post(f"/api/v1/run/{flow_id}", headers=headers, json={"output_type": "text"})
    assert warmup.status_code == status.HTTP_200_OK, warmup.text

    await catalog_policy_service.replace_blocked_component_keys(["ChatInput"], actor_user_id=None)
    db_ledger.statements.clear()
    db_ledger.checkouts = 0
    try:
        response = await client.post(f"/api/v1/run/{flow_id}", headers=headers, json={"output_type": "text"})
        # Snapshot before the unblock below, whose own writes would otherwise land in the ledger.
        run = DbLedger(statements=list(db_ledger.statements), checkouts=db_ledger.checkouts)
    finally:
        await catalog_policy_service.replace_blocked_component_keys([], actor_user_id=None)

    assert response.status_code == status.HTTP_400_BAD_REQUEST, response.text

    print(run.report(f"failing run (status {response.status_code})"))  # noqa: T201

    # Its own budget, not the healthy run's. A rejected run does a fraction of the work, so reusing
    # the healthy ceiling here would leave a test that cannot fail.
    counts = run.by_op_table
    assert counts[("INSERT", "job")] == 0, "a rejected run must not create a job row"
    assert counts[("INSERT", "message")] == 0, "a rejected run must not persist messages"
    assert len(run.statements) <= REJECTED_RUN_BUDGET, run.report("over statement budget")
    assert run.checkouts <= REJECTED_RUN_CHECKOUT_BUDGET, run.report("over checkout budget")

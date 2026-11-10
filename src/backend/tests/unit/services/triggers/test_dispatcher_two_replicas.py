"""Two dispatchers draining one ledger produce one run per event.

This is the epic's central claim, so it is exercised as a soak rather than as a
two-row example: a large batch, two concurrent dispatchers with different owner
tokens (the failover window in which both believe they hold the lease), and an
exact count at the end.

On SQLite the serialization comes from the database's file-level write lock —
which is what protects the several worker processes a single container runs by
default, not merely two coroutines. On Postgres the same guarded UPDATE runs
under ``FOR UPDATE SKIP LOCKED`` candidate scans; set
``LANGFLOW_TEST_DATABASE_URI`` to exercise that path.
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from langflow.services.database.models.trigger.model import TriggerEvent
from langflow.services.database.models.trigger.schemas import TriggerEventState
from langflow.services.deps import session_scope
from langflow.services.triggers import dispatcher, ledger
from sqlmodel import select

pytestmark = pytest.mark.no_blockbuster

SOAK_EVENTS = 1000


async def test_two_dispatchers_draining_one_ledger_submit_each_event_once(
    make_trigger, fake_background_service
) -> None:
    trigger_id = await make_trigger(concurrency_limit=SOAK_EVENTS, max_attempts=1)

    async with session_scope() as session:
        for index in range(SOAK_EVENTS):
            await ledger.append_event(session, trigger_id=trigger_id, dedupe_key=f"soak:{index}")

    async def drain(owner: str) -> None:
        while True:
            dispatched = await dispatcher.run_once(owner=owner)
            if dispatched == 0:
                return
            await asyncio.sleep(0)

    await asyncio.gather(drain("replica-a"), drain("replica-b"))

    async with session_scope() as session:
        rows = (await session.exec(select(TriggerEvent).where(TriggerEvent.trigger_id == trigger_id))).all()

    assert len(rows) == SOAK_EVENTS
    assert {row.state for row in rows} == {TriggerEventState.DISPATCHED.value}
    assert len(fake_background_service.submits) == SOAK_EVENTS

    # Every event produced its own job, and no job id was reused.
    job_ids = {row.job_id for row in rows}
    assert len(job_ids) == SOAK_EVENTS
    idempotency_keys = {submit["request"]["idempotency_key"] for submit in fake_background_service.submits}
    assert len(idempotency_keys) == SOAK_EVENTS


async def test_a_duplicate_tick_from_a_second_replica_never_becomes_a_second_run(
    make_trigger, fake_background_service
) -> None:
    """The unique index absorbs the duplicate before any dispatcher sees it."""
    trigger_id = await make_trigger()
    scheduled = "tick:2026-09-07T08:00:00+00:00"

    async def produce() -> None:
        async with session_scope() as session:
            await ledger.append_event(session, trigger_id=trigger_id, dedupe_key=scheduled)

    await asyncio.gather(produce(), produce(), produce())

    async with session_scope() as session:
        rows = (await session.exec(select(TriggerEvent).where(TriggerEvent.trigger_id == trigger_id))).all()
    assert len(rows) == 1

    await dispatcher.run_once(owner="replica-a")
    assert len(fake_background_service.submits) == 1


class _FakeDialect:
    def __init__(self, name: str) -> None:
        self.name = name


class _FakeBind:
    def __init__(self, name: str) -> None:
        self.dialect = _FakeDialect(name)


class _StatementRecorder:
    """Captures the candidate query without needing a live engine."""

    def __init__(self, dialect_name: str) -> None:
        self.bind = _FakeBind(dialect_name)
        self.statement = None

    async def exec(self, statement):
        self.statement = statement

        class _Result:
            @staticmethod
            def all():
                return []

        return _Result()


@pytest.mark.parametrize(
    ("dialect", "expects_skip_locked"),
    [("postgresql", True), ("sqlite", False)],
)
async def test_the_candidate_scan_uses_skip_locked_only_on_postgres(dialect, expects_skip_locked) -> None:
    """Postgres replicas walk disjoint candidate sets; SQLite has no such clause.

    Correctness on both engines comes from the guarded UPDATE, but without
    SKIP LOCKED two Postgres dispatchers would serialize on the same head rows
    and the soak above would degrade to one effective worker.
    """
    from sqlalchemy.dialects import postgresql, sqlite

    recorder = _StatementRecorder(dialect)
    await dispatcher._candidate_ids(recorder, trigger_id=uuid4(), limit=5)

    compiler = postgresql.dialect() if dialect == "postgresql" else sqlite.dialect()
    rendered = str(recorder.statement.compile(dialect=compiler)).upper()
    assert ("SKIP LOCKED" in rendered) is expects_skip_locked

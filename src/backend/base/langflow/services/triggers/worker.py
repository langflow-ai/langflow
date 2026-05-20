"""The in-process trigger worker.

A single ``asyncio`` task per process drains the ``trigger_job`` queue
and dispatches each row through ``simple_run_flow``. The loop is
spawned in ``main.py`` lifespan; cancellation on shutdown is handled
via an ``asyncio.Event``.

Transaction discipline (the single most important property of this
module): the claim transaction and the terminal transaction are tiny.
The flow execution itself runs **outside** any open transaction. This
is the entire reason Postgres-as-queue scales — long work never holds
a row lock.

Three states per iteration:

1. ``_claim_one`` — short txn. ``SELECT ... FOR UPDATE SKIP LOCKED`` on
   Postgres, optimistic ``UPDATE`` on SQLite. Returns either ``None``
   (queue empty / nothing eligible) or a small dataclass with the
   minimum we need to dispatch.
2. ``_dispatch`` — no txn. Loads the flow and user, builds the
   ``SimplifiedAPIRequest``, calls ``simple_run_flow``. Returns the
   workflow ``Job`` id on success, an exception on failure.
3. ``_finalize_success`` / ``_finalize_failure`` — short txn. Updates
   the row to ``completed`` / ``failed`` and, when applicable, enqueues
   the next ``trigger_job`` row for recurring cron triggers or for the
   retry chain.

The loop swallows every exception except ``CancelledError`` so a
single bad trigger never takes the worker down.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from lfx.log.logger import logger
from sqlalchemy import text
from sqlmodel import select

from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.jobs.model import JobStatus
from langflow.services.database.models.triggers import Trigger, TriggerJob
from langflow.services.database.models.user.model import User
from langflow.services.deps import session_scope
from langflow.services.triggers.scheduler import next_fire_time_utc

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

# Idle/error backoff bounds. Bounded so a recurring minute-level cron
# never waits more than ``_IDLE_BACKOFF_MAX_S`` after its scheduled
# time before the worker notices the new row.
_IDLE_BACKOFF_START_S = 0.5
_IDLE_BACKOFF_MAX_S = 5.0
_ERROR_BACKOFF_S = 10.0

# Per-attempt retry backoff: 2 ** attempt seconds, capped at 5 minutes.
_RETRY_BACKOFF_BASE_S = 2
_RETRY_BACKOFF_CAP_S = 300


@dataclass(frozen=True)
class _ClaimedJob:
    trigger_job_id: UUID
    trigger_id: UUID
    attempt: int
    max_attempts: int


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _retry_delay(attempt: int) -> timedelta:
    """Exponential backoff capped at five minutes."""
    seconds = min(_RETRY_BACKOFF_BASE_S**attempt, _RETRY_BACKOFF_CAP_S)
    return timedelta(seconds=seconds)


async def _claim_one(session: AsyncSession) -> _ClaimedJob | None:
    """Atomically pick the next eligible ``trigger_job`` row and flip it
    to ``in_progress``.

    On Postgres, uses ``FOR UPDATE SKIP LOCKED`` so multiple workers
    can run concurrently without ever handing the same row to two
    workers. On SQLite, uses an optimistic ``UPDATE ... WHERE status =
    'queued'`` which is atomic because SQLite serializes writes.

    Returns ``None`` if no eligible row exists.
    """
    bind = session.get_bind()
    dialect = bind.dialect.name
    now = _utcnow()

    if dialect == "postgresql":
        # Two-step: select the id with row lock, then update. Both
        # statements run inside the same transaction the caller opened
        # via session_scope().
        select_stmt = text(
            "SELECT id, trigger_id, attempt, max_attempts "
            "FROM trigger_job "
            "WHERE status = 'queued' AND scheduled_at <= :now "
            "ORDER BY scheduled_at "
            "LIMIT 1 "
            "FOR UPDATE SKIP LOCKED"
        )
        row = (await session.execute(select_stmt, {"now": now})).first()
        if row is None:
            return None
        trigger_job_id, trigger_id, attempt, max_attempts = row
        await session.execute(
            text(
                "UPDATE trigger_job SET status = 'in_progress', started_at = :now "
                "WHERE id = :id"
            ),
            {"now": now, "id": trigger_job_id},
        )
        return _ClaimedJob(
            trigger_job_id=trigger_job_id,
            trigger_id=trigger_id,
            attempt=attempt,
            max_attempts=max_attempts,
        )

    # SQLite (and any other dialect): one-shot optimistic update. The
    # WHERE clause on ``status`` keeps the claim idempotent if two
    # tasks ever race — only one observes ``status='queued'``.
    update_stmt = text(
        "UPDATE trigger_job "
        "SET status = 'in_progress', started_at = :now "
        "WHERE id = ( "
        "    SELECT id FROM trigger_job "
        "    WHERE status = 'queued' AND scheduled_at <= :now "
        "    ORDER BY scheduled_at "
        "    LIMIT 1 "
        ") "
        "AND status = 'queued' "
        "RETURNING id, trigger_id, attempt, max_attempts"
    )
    result = await session.execute(update_stmt, {"now": now})
    row = result.first()
    if row is None:
        return None
    trigger_job_id, trigger_id, attempt, max_attempts = row
    return _ClaimedJob(
        trigger_job_id=trigger_job_id,
        trigger_id=trigger_id,
        attempt=attempt,
        max_attempts=max_attempts,
    )


async def _load_trigger_and_flow(
    session: AsyncSession,
    trigger_id: UUID,
) -> tuple[Trigger, Flow, User] | None:
    """Return the trigger + its flow + its owning user, or ``None`` if any
    of the three was deleted between claim and dispatch."""
    trigger = (await session.exec(select(Trigger).where(Trigger.id == trigger_id))).first()
    if trigger is None:
        return None
    flow = (await session.exec(select(Flow).where(Flow.id == trigger.flow_id))).first()
    if flow is None:
        return None
    user = (await session.exec(select(User).where(User.id == trigger.user_id))).first()
    if user is None:
        return None
    return trigger, flow, user


async def _run_flow_for_trigger(
    trigger: Trigger,
    flow: Flow,
    user: User,
    trigger_job_id: UUID,
) -> UUID:
    """Invoke ``simple_run_flow`` and return the workflow ``Job`` id.

    Imports happen inside the function so this module does not pull
    the full request-handling stack at import time (which would create
    a circular import with ``api.v1.endpoints``).
    """
    from langflow.api.v1.endpoints import simple_run_flow
    from langflow.api.v1.schemas import SimplifiedAPIRequest

    payload = dict(trigger.payload or {})
    input_request = SimplifiedAPIRequest(
        input_value=payload.get("input_value"),
        input_type=payload.get("input_type"),
        output_type=payload.get("output_type"),
        output_component=payload.get("output_component"),
        tweaks=payload.get("tweaks"),
        session_id=payload.get("session_id"),
    )
    run_id = str(uuid4())
    await simple_run_flow(
        flow=flow,
        input_request=input_request,
        stream=False,
        api_key_user=user,
        event_manager=None,
        context={
            "trigger_id": str(trigger.id),
            "trigger_job_id": str(trigger_job_id),
        },
        run_id=run_id,
    )
    return UUID(run_id)


async def _enqueue_next_cron_job(session: AsyncSession, trigger: Trigger, after: datetime) -> None:
    """Insert the next ``trigger_job`` for a recurring trigger.

    No-op if the trigger has been disabled or if it has no cron
    expression. Called inside the terminal transaction so the new row
    is visible to the next iteration immediately.
    """
    if not trigger.is_active or trigger.cron_expression is None:
        return
    next_fire = next_fire_time_utc(
        cron_expression=trigger.cron_expression,
        timezone_name=trigger.timezone,
        after=after,
    )
    session.add(
        TriggerJob(
            id=uuid4(),
            trigger_id=trigger.id,
            status=JobStatus.QUEUED,
            scheduled_at=next_fire,
            attempt=1,
            max_attempts=trigger.max_attempts,
            created_at=after,
        ),
    )


async def _enqueue_retry(session: AsyncSession, trigger: Trigger, claimed: _ClaimedJob, *, after: datetime) -> None:
    """Insert a retry ``trigger_job`` row with ``attempt+1``."""
    session.add(
        TriggerJob(
            id=uuid4(),
            trigger_id=trigger.id,
            status=JobStatus.QUEUED,
            scheduled_at=after + _retry_delay(claimed.attempt),
            attempt=claimed.attempt + 1,
            max_attempts=claimed.max_attempts,
            created_at=after,
        ),
    )


async def _finalize_success(
    session: AsyncSession,
    claimed: _ClaimedJob,
    trigger: Trigger,
    *,
    run_job_id: UUID,
) -> None:
    now = _utcnow()
    job = (await session.exec(select(TriggerJob).where(TriggerJob.id == claimed.trigger_job_id))).first()
    if job is None:
        # Trigger (and cascading jobs) were deleted while the flow ran.
        return
    job.status = JobStatus.COMPLETED
    job.finished_at = now
    job.run_job_id = run_job_id
    session.add(job)
    await _enqueue_next_cron_job(session, trigger, after=now)


async def _finalize_failure(
    session: AsyncSession,
    claimed: _ClaimedJob,
    trigger: Trigger,
    *,
    error: str,
) -> None:
    now = _utcnow()
    job = (await session.exec(select(TriggerJob).where(TriggerJob.id == claimed.trigger_job_id))).first()
    if job is None:
        return
    job.status = JobStatus.FAILED
    job.finished_at = now
    job.error = error[:4000]  # bound the column write; full traceback also goes to logs
    session.add(job)
    if claimed.attempt < claimed.max_attempts:
        await _enqueue_retry(session, trigger, claimed, after=now)
        return
    # Out of retry budget — for recurring cron triggers we still want
    # the *next* scheduled fire to be enqueued so a transient outage
    # does not stop the schedule permanently.
    await _enqueue_next_cron_job(session, trigger, after=now)


async def _dispatch(claimed: _ClaimedJob) -> None:
    """Execute the flow for a claimed trigger_job row.

    Opens fresh sessions for load, run, and finalize so the flow run
    never blocks a DB connection.
    """
    # 1. Load (short txn).
    async with session_scope() as session:
        loaded = await _load_trigger_and_flow(session, claimed.trigger_id)
    if loaded is None:
        # Trigger was deleted between claim and dispatch. Nothing to do —
        # the trigger_job row was either cascade-deleted with the trigger
        # or the user disabled the trigger; either way we leave the
        # ``in_progress`` row to be tidied up by the startup reset hook.
        await logger.adebug("trigger_job %s: trigger gone before dispatch", claimed.trigger_job_id)
        return
    trigger, flow, user = loaded

    # 2. Run (no txn).
    try:
        run_job_id = await _run_flow_for_trigger(trigger, flow, user, claimed.trigger_job_id)
    except Exception as exc:  # noqa: BLE001 — worker must always finalize
        await logger.aexception(
            "trigger_job %s failed on attempt %d/%d",
            claimed.trigger_job_id,
            claimed.attempt,
            claimed.max_attempts,
        )
        async with session_scope() as session:
            await _finalize_failure(session, claimed, trigger, error=repr(exc))
        return

    # 3. Finalize success (short txn).
    async with session_scope() as session:
        await _finalize_success(session, claimed, trigger, run_job_id=run_job_id)
    await logger.ainfo(
        "trigger_job %s completed (trigger=%s, run_job=%s)",
        claimed.trigger_job_id,
        claimed.trigger_id,
        run_job_id,
    )


async def trigger_worker_loop(stop_event: asyncio.Event) -> None:
    """Drain the trigger_job queue until ``stop_event`` is set.

    Spawned from ``main.py`` lifespan with::

        stop_event = asyncio.Event()
        task = asyncio.create_task(trigger_worker_loop(stop_event))
        # ... on shutdown ...
        stop_event.set()
        task.cancel()

    The two cancellation paths (``stop_event`` and ``task.cancel``)
    are both honoured.
    """
    idle_backoff = _IDLE_BACKOFF_START_S
    await logger.ainfo("trigger worker started")
    while not stop_event.is_set():
        try:
            async with session_scope() as session:
                claimed = await _claim_one(session)
            if claimed is None:
                # Quiet queue: wait, bounded.
                await _sleep_with_stop(stop_event, idle_backoff)
                idle_backoff = min(idle_backoff * 2, _IDLE_BACKOFF_MAX_S)
                continue
            idle_backoff = _IDLE_BACKOFF_START_S
            await _dispatch(claimed)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — never let the loop die
            await logger.aexception("trigger worker iteration failed")
            await _sleep_with_stop(stop_event, _ERROR_BACKOFF_S)
    await logger.ainfo("trigger worker exiting")


async def _sleep_with_stop(stop_event: asyncio.Event, seconds: float) -> None:
    """Sleep but wake immediately if the stop event is set."""
    try:
        await asyncio.wait_for(stop_event.wait(), timeout=seconds)
    except asyncio.TimeoutError:  # noqa: PERF203 — TimeoutError is the happy path
        pass


# --------------------------------------------------------------------------- #
#  Startup hook                                                                #
# --------------------------------------------------------------------------- #


async def recover_stalled_jobs(*, older_than: timedelta = timedelta(minutes=30)) -> int:
    """Reset ``in_progress`` trigger_job rows older than ``older_than``.

    Crude orphan recovery: if a worker crashed mid-flow the row stays
    ``in_progress`` forever. Run once at process startup to flip such
    rows back to ``queued`` so the worker picks them up again. The
    ``attempt`` counter is not incremented — the previous run never
    finalized, so it does not consume the retry budget.
    """
    from langflow.services.database.models.triggers.crud import reset_stalled_in_progress

    cutoff = _utcnow() - older_than
    async with session_scope() as session:
        count = await reset_stalled_in_progress(session, older_than=cutoff)
    if count:
        await logger.ainfo("trigger worker: reset %d stalled in_progress trigger_job rows", count)
    return count

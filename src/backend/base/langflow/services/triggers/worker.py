"""The in-process trigger worker.

One ``asyncio`` task per process drains ``trigger_job`` and dispatches
each row through ``simple_run_flow``. Configuration is **always** read
live from ``flow.data`` at dispatch time — never cached on the
trigger_job row. This means a user editing the cron in the canvas
sees the change applied at the next fire without any reconciliation
step on our side.

Transaction discipline (the single most important property of this
module): the claim transaction and the terminal transaction are tiny.
The flow execution itself runs **outside** any open transaction. That
is the only safe way to run Postgres-as-queue at scale — long work
never holds a row lock.

Three steps per iteration:

1. ``_claim_one`` — short txn. ``SELECT ... FOR UPDATE SKIP LOCKED`` on
   Postgres, optimistic ``UPDATE ... WHERE status='queued'`` on SQLite.
   Returns a small dataclass with the queue row identity and the
   ``(flow_id, component_id)`` pointer the next steps will dereference.
2. ``_dispatch`` — no txn. Loads the flow + user, looks up the live
   config via :mod:`langflow.services.triggers.discovery`, builds the
   ``SimplifiedAPIRequest`` tweaks via
   :mod:`langflow.services.triggers.tweaks`, calls ``simple_run_flow``.
3. ``_finalize_success`` / ``_finalize_failure`` — short txn. Updates
   the row to terminal status and either enqueues the next cron fire
   (success path) or the next retry attempt (failure path, until the
   budget is exhausted, after which the next cron fire is enqueued
   anyway so a transient outage does not stop the schedule).

The loop swallows every exception except ``CancelledError`` so a
single bad trigger cannot take the worker down.
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from lfx.log.logger import logger
from sqlalchemy import text
from sqlmodel import select

from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.jobs.model import JobStatus
from langflow.services.database.models.triggers import TriggerJob
from langflow.services.database.models.user.model import User
from langflow.services.deps import session_scope
from langflow.services.triggers._sqlmodel_compat import suppress_sqlmodel_exec_warning
from langflow.services.triggers.discovery import (
    CronTriggerConfig,
    find_cron_trigger_configs,
)
from langflow.services.triggers.scheduler import next_fire_time_utc

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

# Idle backoff caps idle queue polling so a minute-level cron is never
# delayed by more than ``_IDLE_BACKOFF_MAX_S`` after its scheduled tick.
_IDLE_BACKOFF_START_S = 0.5
_IDLE_BACKOFF_MAX_S = 5.0
_ERROR_BACKOFF_S = 10.0

# Per-attempt retry backoff: 2 ** attempt seconds, capped at 5 minutes.
_RETRY_BACKOFF_BASE_S = 2
_RETRY_BACKOFF_CAP_S = 300


@dataclass(frozen=True)
class _ClaimedJob:
    trigger_job_id: UUID
    flow_id: UUID
    component_id: str
    attempt: int
    max_attempts: int


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _retry_delay(attempt: int) -> timedelta:
    """Exponential backoff capped at five minutes."""
    seconds = min(_RETRY_BACKOFF_BASE_S**attempt, _RETRY_BACKOFF_CAP_S)
    return timedelta(seconds=seconds)


def _coerce_uuid(value: object) -> UUID:
    """Normalize a raw SQL row value to a ``UUID``.

    SQLAlchemy returns ``UUID`` for ORM queries against ``sa.Uuid()``
    columns but a hex string (or bytes) for ``text()`` queries since
    raw SQL bypasses the type adapter. The worker uses ``text()`` for
    the claim query — coerce here so downstream callers can compare
    against ORM Uuid columns without surprises.
    """
    if isinstance(value, UUID):
        return value
    if isinstance(value, bytes):
        return UUID(bytes=value)
    return UUID(str(value))


async def _claim_one(session: AsyncSession) -> _ClaimedJob | None:
    """Atomically claim the next eligible ``trigger_job`` row.

    Flips the chosen row to ``in_progress``. On Postgres uses
    ``FOR UPDATE SKIP LOCKED`` so multiple workers can run concurrently
    without ever handing the same row to two workers. On SQLite uses
    an optimistic ``UPDATE ... WHERE status = 'queued'`` which is atomic
    because SQLite serialises writes.

    Returns ``None`` when no eligible row exists.
    """
    bind = session.get_bind()
    dialect = bind.dialect.name
    now = _utcnow()

    if dialect == "postgresql":
        select_stmt = text(
            "SELECT id, flow_id, component_id, attempt, max_attempts "
            "FROM trigger_job "
            "WHERE status = 'queued' AND scheduled_at <= :now "
            "ORDER BY scheduled_at "
            "LIMIT 1 "
            "FOR UPDATE SKIP LOCKED"
        )
        with suppress_sqlmodel_exec_warning():
            row = (await session.execute(select_stmt, {"now": now})).first()
        if row is None:
            return None
        trigger_job_id, flow_id, component_id, attempt, max_attempts = row
        with suppress_sqlmodel_exec_warning():
            await session.execute(
                text(
                    "UPDATE trigger_job SET status = 'in_progress', started_at = :now "
                    "WHERE id = :id"
                ),
                {"now": now, "id": trigger_job_id},
            )
        return _ClaimedJob(
            trigger_job_id=_coerce_uuid(trigger_job_id),
            flow_id=_coerce_uuid(flow_id),
            component_id=str(component_id),
            attempt=attempt,
            max_attempts=max_attempts,
        )

    # SQLite (and any other dialect): one-shot optimistic update.
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
        "RETURNING id, flow_id, component_id, attempt, max_attempts"
    )
    with suppress_sqlmodel_exec_warning():
        result = await session.execute(update_stmt, {"now": now})
    row = result.first()
    if row is None:
        return None
    trigger_job_id, flow_id, component_id, attempt, max_attempts = row
    return _ClaimedJob(
        trigger_job_id=_coerce_uuid(trigger_job_id),
        flow_id=_coerce_uuid(flow_id),
        component_id=str(component_id),
        attempt=attempt,
        max_attempts=max_attempts,
    )


@dataclass(frozen=True)
class _DispatchContext:
    """What ``_dispatch`` needs to execute a fire.

    Loaded inside a short txn so the flow execution itself runs after
    the connection is back in the pool.
    """

    flow: Flow
    user: User
    config: CronTriggerConfig


async def _load_dispatch_context(
    session: AsyncSession,
    claimed: _ClaimedJob,
) -> _DispatchContext | None:
    """Return the flow + user + live component config, or ``None``.

    Returns ``None`` whenever any of (flow, user, component) cannot be
    resolved — flow deleted, user deleted, or the component removed
    from ``flow.data``. The caller treats these as "trigger gone" and
    skips the finalize step (the row will be cleaned up by the next
    save's reconciliation, or by the CASCADE on the flow delete).
    """
    flow = (
        await session.exec(select(Flow).where(Flow.id == claimed.flow_id))
    ).first()
    if flow is None:
        return None

    configs = find_cron_trigger_configs(flow.data)
    matching = next(
        (c for c in configs if c.component_id == claimed.component_id),
        None,
    )
    if matching is None:
        return None

    user_id = flow.user_id
    if user_id is None:
        return None
    user = (await session.exec(select(User).where(User.id == user_id))).first()
    if user is None:
        return None

    return _DispatchContext(flow=flow, user=user, config=matching)


async def _run_flow_for_trigger(
    ctx: _DispatchContext,
    claimed: _ClaimedJob,
    *,
    fire_time: datetime,
) -> UUID:
    """Invoke ``simple_run_flow`` and return the workflow ``Job`` id.

    Imports happen inside the function so the worker module does not
    pull the full request-handling stack at import time (which would
    create a circular import with ``api.v1.endpoints``).

    The trigger does not feed input data into the flow — it just
    kicks the whole graph off. We dispatch with a default-empty
    ``SimplifiedAPIRequest`` so the flow runs against its own inputs
    (ChatInput defaults, hardcoded values, etc.). The fire time is
    surfaced only via the ``context`` dict, which the existing
    tracing / telemetry hooks already consume.
    """
    from langflow.api.v1.endpoints import simple_run_flow
    from langflow.api.v1.schemas import SimplifiedAPIRequest

    run_id = str(uuid4())
    await simple_run_flow(
        flow=ctx.flow,
        input_request=SimplifiedAPIRequest(),
        stream=False,
        api_key_user=ctx.user,
        event_manager=None,
        context={
            "trigger_component_id": ctx.config.component_id,
            "trigger_job_id": str(claimed.trigger_job_id),
            "trigger_fire_time": fire_time.isoformat(),
        },
        run_id=run_id,
    )
    return UUID(run_id)


async def _enqueue_next_cron_job(
    session: AsyncSession,
    claimed: _ClaimedJob,
    ctx: _DispatchContext,
    *,
    after: datetime,
) -> None:
    """Insert the next ``trigger_job`` for the same ``(flow_id, component_id)``.

    Uses the **live** config because ``ctx.config`` was just freshly
    parsed from ``flow.data``. If the user edited the cron between
    enqueue and this finalize step, the new value takes effect now.
    """
    next_fire = next_fire_time_utc(
        cron_expression=ctx.config.cron_expression,
        timezone_name=ctx.config.timezone,
        after=after,
    )
    session.add(
        TriggerJob(
            id=uuid4(),
            flow_id=claimed.flow_id,
            component_id=claimed.component_id,
            status=JobStatus.QUEUED,
            scheduled_at=next_fire,
            attempt=1,
            max_attempts=ctx.config.max_attempts,
            created_at=after,
        ),
    )


async def _enqueue_retry(
    session: AsyncSession,
    claimed: _ClaimedJob,
    *,
    after: datetime,
) -> None:
    """Insert a retry ``trigger_job`` row with ``attempt+1``."""
    session.add(
        TriggerJob(
            id=uuid4(),
            flow_id=claimed.flow_id,
            component_id=claimed.component_id,
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
    ctx: _DispatchContext,
    *,
    run_job_id: UUID,
) -> None:
    now = _utcnow()
    job = (
        await session.exec(select(TriggerJob).where(TriggerJob.id == claimed.trigger_job_id))
    ).first()
    if job is None:
        return
    job.status = JobStatus.COMPLETED
    job.finished_at = now
    job.run_job_id = run_job_id
    session.add(job)
    await _enqueue_next_cron_job(session, claimed, ctx, after=now)


async def _finalize_failure(
    session: AsyncSession,
    claimed: _ClaimedJob,
    ctx: _DispatchContext | None,
    *,
    error: str,
) -> None:
    now = _utcnow()
    job = (
        await session.exec(select(TriggerJob).where(TriggerJob.id == claimed.trigger_job_id))
    ).first()
    if job is None:
        return
    job.status = JobStatus.FAILED
    job.finished_at = now
    job.error = error[:4000]
    session.add(job)
    if claimed.attempt < claimed.max_attempts:
        await _enqueue_retry(session, claimed, after=now)
        return
    # Out of retry budget — for recurring cron triggers we still want
    # the next scheduled fire enqueued so a transient outage does not
    # stop the schedule permanently. We can only do that if we still
    # have the context (component config) — without it the trigger is
    # effectively gone and there is nothing to reschedule.
    if ctx is not None:
        await _enqueue_next_cron_job(session, claimed, ctx, after=now)


async def _dispatch(claimed: _ClaimedJob) -> None:
    """Execute the flow for a claimed trigger_job row."""
    fire_time = _utcnow()
    async with session_scope() as session:
        ctx = await _load_dispatch_context(session, claimed)
    if ctx is None:
        await logger.adebug(
            "trigger_job %s: trigger gone before dispatch (flow=%s component=%s)",
            claimed.trigger_job_id,
            claimed.flow_id,
            claimed.component_id,
        )
        # Mark the row as cancelled so it doesn't sit forever in
        # in_progress. Without context we cannot reschedule.
        async with session_scope() as session:
            await _finalize_failure(session, claimed, None, error="trigger gone before dispatch")
        return

    try:
        run_job_id = await _run_flow_for_trigger(ctx, claimed, fire_time=fire_time)
    except Exception as exc:  # noqa: BLE001 — worker must always finalize
        await logger.aexception(
            "trigger_job %s failed on attempt %d/%d (flow=%s component=%s)",
            claimed.trigger_job_id,
            claimed.attempt,
            claimed.max_attempts,
            claimed.flow_id,
            claimed.component_id,
        )
        async with session_scope() as session:
            await _finalize_failure(session, claimed, ctx, error=repr(exc))
        return

    async with session_scope() as session:
        await _finalize_success(session, claimed, ctx, run_job_id=run_job_id)
    await logger.ainfo(
        "trigger_job %s completed (flow=%s component=%s run_job=%s)",
        claimed.trigger_job_id,
        claimed.flow_id,
        claimed.component_id,
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

    Both cancellation paths are honoured.
    """
    idle_backoff = _IDLE_BACKOFF_START_S
    await logger.ainfo("trigger worker started")
    while not stop_event.is_set():
        try:
            async with session_scope() as session:
                claimed = await _claim_one(session)
            if claimed is None:
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
    with contextlib.suppress(asyncio.TimeoutError):
        await asyncio.wait_for(stop_event.wait(), timeout=seconds)


# --------------------------------------------------------------------------- #
#  Startup hook                                                                #
# --------------------------------------------------------------------------- #


async def recover_stalled_jobs(*, older_than: timedelta = timedelta(minutes=30)) -> int:
    """Reset ``in_progress`` trigger_job rows older than ``older_than``.

    Crude orphan recovery: if a worker crashed mid-flow the row stays
    ``in_progress`` forever. Run once at process startup to flip such
    rows back to ``queued`` so the worker picks them up again. The
    ``attempt`` counter is not incremented — the prior run never
    finalized, so it does not consume the retry budget.
    """
    from langflow.services.database.models.triggers.crud import reset_stalled_in_progress

    cutoff = _utcnow() - older_than
    async with session_scope() as session:
        count = await reset_stalled_in_progress(session, older_than=cutoff)
    if count:
        await logger.ainfo("trigger worker: reset %d stalled in_progress trigger_job rows", count)
    return count

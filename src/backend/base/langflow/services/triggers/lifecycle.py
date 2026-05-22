"""Flow-save side effects for trigger components.

Called once per flow save (insert / update / patch). Responsible for
keeping the ``trigger_job`` work queue in sync with the CronTrigger
components present in ``flow.data``:

* Nodes that newly appear in the flow → enqueue an initial trigger_job
  scheduled at the next cron tick.
* Nodes that disappear from the flow → mark their queued trigger_jobs
  as ``cancelled`` (history preserved; worker stops considering them).
* Existing nodes whose cron expression or timezone changed → cancel
  the stale queued row and enqueue a fresh one at the new next fire.
  Drift is detected by recomputing ``next_fire_time_utc(after=
  job.created_at)`` from the current canvas config and comparing it
  to the stored ``scheduled_at``. The function is deterministic, so
  any mismatch means the user edited the trigger inputs between the
  enqueue and this save. Without this step the in-flight job keeps
  firing on the old schedule until it completes, which contradicts
  the value the UI now displays for the trigger.
* Existing nodes whose schedule did not change are left alone — the
  worker reads the live config from ``flow.data`` on each dispatch
  anyway (so ``max_attempts`` edits land at the next fire without us
  touching the row).

Invalid configurations (bad cron expression, unknown IANA timezone)
are skipped silently and the operation is logged. We do not raise
because that would block the flow save itself; the user can fix the
field in the canvas and the next save will re-evaluate.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from lfx.log.logger import logger
from sqlmodel import select

from langflow.services.database.models.jobs.model import JobStatus
from langflow.services.database.models.triggers.crud import (
    cancel_queued_jobs_for_components,
)
from langflow.services.database.models.triggers.model import TriggerJob
from langflow.services.triggers.discovery import (
    CronTriggerConfig,
    find_cron_trigger_configs,
)
from langflow.services.triggers.scheduler import (
    InvalidTriggerConfigError,
    next_fire_time_utc,
    validate_trigger_config,
)

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.database.models.flow.model import Flow


async def _existing_queued_jobs_by_component(
    session: AsyncSession,
    flow_id,
) -> dict[str, TriggerJob]:
    """Return the QUEUED trigger_job per component for ``flow_id``.

    There can only be one queued job per ``(flow_id, component_id)``
    at a time (the worker enqueues the next fire on finalize), so a
    plain dict is the right shape for the reconcile diff. If an older
    bug left multiple queued rows behind, the last one wins for
    drift-detection purposes — the duplicates would get cancelled
    anyway by ``cancel_queued_jobs_for_components`` once the user
    edits the trigger.
    """
    statement = select(TriggerJob).where(
        TriggerJob.flow_id == flow_id,
        TriggerJob.status == JobStatus.QUEUED,
    )
    result = await session.exec(statement)
    return {job.component_id: job for job in result.all()}


def _as_utc(dt: datetime) -> datetime:
    """Coerce a possibly-naive datetime to a tz-aware UTC datetime.

    SQLite drops the ``tzinfo`` of ``DateTime(timezone=True)`` columns
    on read, so values that were written tz-aware can come back naive.
    The downstream ``croniter`` math (and equality with the freshly
    computed next fire) only works correctly if both sides agree on
    tz-awareness, so we normalise everything to UTC at the boundary.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _schedule_drifted(
    job: TriggerJob,
    config: CronTriggerConfig,
) -> bool:
    """``True`` if ``job.scheduled_at`` no longer matches ``config``.

    Recomputes the next fire that *would* have been scheduled at
    enqueue time (``after=job.created_at``) from the current cron
    expression and timezone, and compares it against the stored
    value. Because ``next_fire_time_utc`` is deterministic for a
    given ``(cron, tz, anchor)``, equality means the config has not
    been touched since the row was written; inequality means the
    user edited the canvas and we should reschedule.

    Invalid configs (bad cron / unknown tz) return ``False`` here —
    drift detection is not the right place to surface that, the
    ``new_ids`` path already logs and skips invalid configs and the
    stale queued row stays put until the user fixes the inputs.
    """
    try:
        expected = next_fire_time_utc(
            cron_expression=config.cron_expression,
            timezone_name=config.timezone,
            after=_as_utc(job.created_at),
        )
    except InvalidTriggerConfigError:
        return False
    return expected != _as_utc(job.scheduled_at)


async def _enqueue_initial_job(
    session: AsyncSession,
    flow_id,
    config: CronTriggerConfig,
    *,
    now: datetime,
) -> None:
    """Insert a single queued trigger_job for ``(flow_id, component_id)``.

    Caller has already validated the cron + timezone — the function is
    intentionally narrow so the validation lives at exactly one layer.
    """
    next_fire = next_fire_time_utc(
        cron_expression=config.cron_expression,
        timezone_name=config.timezone,
        after=now,
    )
    session.add(
        TriggerJob(
            id=uuid4(),
            flow_id=flow_id,
            component_id=config.component_id,
            status=JobStatus.QUEUED,
            scheduled_at=next_fire,
            attempt=1,
            max_attempts=config.max_attempts,
            created_at=now,
        ),
    )


async def reconcile_trigger_jobs_for_flow(
    session: AsyncSession,
    flow: Flow,
) -> None:
    """Bring ``trigger_job`` in line with the current ``flow.data``.

    Idempotent: calling twice with the same flow state is a no-op
    after the first call. Safe to invoke on every save without rate
    limiting.

    Errors discovered per-component (invalid cron / timezone) are
    logged and do not interrupt the save — the flow row is still
    written, the offending trigger just does not get a queued job
    until the user corrects its inputs.
    """
    now = datetime.now(timezone.utc)
    flow_data = flow.data if flow.data else None

    desired = find_cron_trigger_configs(flow_data)
    desired_by_id = {c.component_id: c for c in desired if c.component_id}

    existing_by_id = await _existing_queued_jobs_by_component(session, flow.id)
    existing_ids = set(existing_by_id.keys())

    # Components that disappeared from the canvas → cancel their queued jobs.
    removed_ids = existing_ids - set(desired_by_id.keys())
    if removed_ids:
        cancelled = await cancel_queued_jobs_for_components(
            session,
            flow.id,
            sorted(removed_ids),
        )
        if cancelled:
            await logger.adebug(
                "trigger lifecycle: cancelled %d queued job(s) on flow %s for removed components %s",
                cancelled,
                flow.id,
                sorted(removed_ids),
            )

    # Existing components whose cron / timezone changed → cancel the
    # stale queued row and treat the component as new below so it gets
    # re-enqueued on the new schedule.
    drifted_ids: list[str] = [
        component_id
        for component_id in sorted(existing_ids & set(desired_by_id.keys()))
        if _schedule_drifted(existing_by_id[component_id], desired_by_id[component_id])
    ]
    if drifted_ids:
        cancelled = await cancel_queued_jobs_for_components(
            session,
            flow.id,
            drifted_ids,
        )
        if cancelled:
            await logger.adebug(
                "trigger lifecycle: cancelled %d drifted queued job(s) on flow %s for components %s",
                cancelled,
                flow.id,
                drifted_ids,
            )

    # Components that appeared (no existing queued job) → enqueue first fire.
    # Drifted components fall into this branch too: their stale rows were
    # just cancelled, so they no longer count as "existing" from here on.
    new_ids = (set(desired_by_id.keys()) - existing_ids) | set(drifted_ids)
    for component_id in sorted(new_ids):
        config = desired_by_id[component_id]
        try:
            validate_trigger_config(
                cron_expression=config.cron_expression,
                timezone_name=config.timezone,
            )
        except InvalidTriggerConfigError as exc:
            await logger.awarning(
                "trigger lifecycle: skipping enqueue for flow %s component %s — %s",
                flow.id,
                component_id,
                exc,
            )
            continue
        await _enqueue_initial_job(session, flow.id, config, now=now)

"""Flow-save side effects for trigger components.

Called once per flow save (insert / update / patch). Responsible for
keeping the ``trigger_job`` work queue in sync with the CronTrigger
components present in ``flow.data``:

* Nodes that newly appear in the flow → enqueue an initial trigger_job
  scheduled at the next cron tick.
* Nodes that disappear from the flow → mark their queued trigger_jobs
  as ``cancelled`` (history preserved; worker stops considering them).
* Existing nodes are left alone — the worker reads the live config
  from ``flow.data`` on each dispatch, so cron / timezone edits in the
  canvas are picked up at the next fire automatically and we do not
  need to mutate the already-queued row.

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


async def _existing_queued_component_ids(
    session: AsyncSession,
    flow_id,
) -> set[str]:
    statement = select(TriggerJob.component_id).where(
        TriggerJob.flow_id == flow_id,
        TriggerJob.status == JobStatus.QUEUED,
    )
    result = await session.exec(statement)
    return set(result.all())


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

    existing_ids = await _existing_queued_component_ids(session, flow.id)

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

    # Components that appeared (no existing queued job) → enqueue first fire.
    new_ids = set(desired_by_id.keys()) - existing_ids
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

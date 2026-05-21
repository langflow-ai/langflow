"""Read-only aggregator queries for the triggers HTTP surface.

Walks every flow the current user owns, surfaces the CronTrigger
components present in their saved JSON, and joins each component
with its most recent ``trigger_job`` row(s). The HTTP layer hands
the result straight to the frontend list view.

Kept separate from the route handlers so the query logic can be
exercised in unit tests without standing up a FastAPI client.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlmodel import col, select

from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.jobs.model import JobStatus
from langflow.services.database.models.triggers.model import TriggerJob
from langflow.services.triggers.discovery import (
    CronTriggerConfig,
    find_cron_trigger_configs,
)

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession


@dataclass(frozen=True)
class TriggerInstance:
    """One CronTrigger component instance surfaced to the API.

    Combines the component config (live, from ``flow.data``) with two
    cached views into the work queue:

    * ``next_fire_at`` — when the worker will pick up the next queued
      job for this component, if any.
    * ``last_finished_status`` / ``last_finished_at`` — the most
      recent terminal job (completed / failed / cancelled / timed_out)
      for this component, for the "last run" column in the UI.

    All fields are derived; nothing here is persisted in this shape.
    """

    flow_id: UUID
    flow_name: str
    component_id: str
    cron_expression: str
    timezone: str
    max_attempts: int
    next_fire_at: datetime | None
    last_finished_status: JobStatus | None
    last_finished_at: datetime | None


_TERMINAL_STATES: tuple[JobStatus, ...] = (
    JobStatus.COMPLETED,
    JobStatus.FAILED,
    JobStatus.CANCELLED,
    JobStatus.TIMED_OUT,
)


async def _user_flows_with_data(session: AsyncSession, user_id: UUID) -> list[Flow]:
    """Return user-owned flows that have ``flow.data`` populated.

    Filters NULL/empty data server-side so the Python iteration only
    sees rows worth inspecting.
    """
    statement = select(Flow).where(
        Flow.user_id == user_id,
        col(Flow.data).is_not(None),
    )
    result = await session.exec(statement)
    return list(result.all())


async def _jobs_for_components(
    session: AsyncSession,
    flow_id: UUID,
    component_ids: list[str],
) -> dict[str, list[TriggerJob]]:
    """Group existing trigger_job rows by component_id for one flow.

    Returns ``{component_id: [TriggerJob, ...]}`` ordered with the most
    recently-scheduled jobs first so the aggregator can grab "next
    queued" and "last finished" with simple list comprehensions.
    """
    if not component_ids:
        return {}
    statement = (
        select(TriggerJob)
        .where(
            TriggerJob.flow_id == flow_id,
            col(TriggerJob.component_id).in_(component_ids),
        )
        .order_by(col(TriggerJob.scheduled_at).desc())
    )
    result = await session.exec(statement)
    by_component: dict[str, list[TriggerJob]] = {cid: [] for cid in component_ids}
    for job in result.all():
        by_component.setdefault(job.component_id, []).append(job)
    return by_component


def _summarise(
    flow: Flow,
    config: CronTriggerConfig,
    jobs: list[TriggerJob],
) -> TriggerInstance:
    """Combine one component's config with its job history into a TriggerInstance."""
    next_fire = next(
        (j.scheduled_at for j in reversed(jobs) if j.status == JobStatus.QUEUED),
        None,
    )
    last_terminal = next(
        (j for j in jobs if j.status in _TERMINAL_STATES),
        None,
    )
    return TriggerInstance(
        flow_id=flow.id,
        flow_name=flow.name,
        component_id=config.component_id,
        cron_expression=config.cron_expression,
        timezone=config.timezone,
        max_attempts=config.max_attempts,
        next_fire_at=next_fire,
        last_finished_status=last_terminal.status if last_terminal else None,
        last_finished_at=last_terminal.finished_at if last_terminal else None,
    )


async def list_triggers_for_user(
    session: AsyncSession,
    user_id: UUID,
) -> list[TriggerInstance]:
    """Surface every CronTrigger component owned by ``user_id``.

    O(F) flows + O(F) job batches — one query per flow that has
    triggers. The volume of triggers a single user creates is bounded
    by hand-editing the canvas, so we trade query count for simplicity.
    """
    flows = await _user_flows_with_data(session, user_id)

    instances: list[TriggerInstance] = []
    for flow in flows:
        configs = find_cron_trigger_configs(flow.data)
        if not configs:
            continue
        jobs_by_component = await _jobs_for_components(
            session,
            flow.id,
            [c.component_id for c in configs],
        )
        instances.extend(
            _summarise(flow, config, jobs_by_component.get(config.component_id, []))
            for config in configs
        )

    # Stable order: flow name first, then component id within the flow.
    instances.sort(key=lambda i: (i.flow_name.lower(), i.component_id))
    return instances

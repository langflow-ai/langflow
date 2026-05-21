"""Persistence for the in-flow trigger feature.

The schedule itself lives in ``flow.data`` as a ``CronTrigger`` node;
this module only owns the **work queue** rows that the in-process
worker drains. There is no parallel ``trigger`` table: the source of
truth for "should this fire?" is the presence of the component inside
a flow, not a row in a registry.

``TriggerJob`` columns:

* ``id`` — primary key.
* ``flow_id`` — owning flow. ``ON DELETE CASCADE`` so deleting the
  flow purges its queued jobs.
* ``component_id`` — the node id in ``flow.data`` (e.g.
  ``"CronTrigger-abc12"``). The worker reads the live cron config
  from this node on each dispatch — config edits in the canvas are
  picked up automatically.
* ``status`` — reuses the existing :class:`JobStatus` enum so the
  observability surface stays uniform with the rest of the system.
* ``scheduled_at`` — when the worker may claim the row.
* ``started_at`` / ``finished_at`` — instrumentation for dispatch.
* ``attempt`` / ``max_attempts`` — retry budget snapshot. Editing the
  component's ``max_attempts`` after a fire does not retroactively
  alter the in-flight retry chain.
* ``error`` — last error message on failure.
* ``run_job_id`` — cross-link to the existing ``job`` row that
  ``simple_run_flow`` creates for the actual graph execution. Nullable
  because it is only set once dispatch starts.
* ``created_at`` — enqueue timestamp.

The composite index ``(status, scheduled_at)`` is the planner's hot
path for the worker's claim query.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import Column, DateTime, ForeignKey, Text
from sqlalchemy import Enum as SQLEnum
from sqlmodel import Field, SQLModel

from langflow.services.database.models.jobs.model import JobStatus


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TriggerJobBase(SQLModel):
    id: UUID = Field(default_factory=uuid4, primary_key=True)

    # FK + index: deleting a flow cascades to its queued jobs.
    flow_id: UUID = Field(
        sa_column=Column(
            sa.Uuid(),
            ForeignKey("flow.id", ondelete="CASCADE"),
            index=True,
            nullable=False,
        ),
    )

    # The node id in ``flow.data["nodes"][*].id`` for the originating
    # trigger component. String, not UUID — the canvas builds these as
    # ``"<ClassName>-<5char-hex>"``. Indexed to support "all jobs for
    # this component" lookups (cancel-on-removal, history view).
    component_id: str = Field(
        sa_column=Column(sa.String(), nullable=False, index=True),
    )

    # Reuses the existing ``job_status_enum`` Postgres type. The
    # ``create_type=False`` flag keeps Alembic from issuing a second
    # ``CREATE TYPE`` on Postgres — the type is owned by the original
    # ``job`` migration. On SQLite the column is a checked string and
    # the flag is a no-op.
    status: JobStatus = Field(
        default=JobStatus.QUEUED,
        sa_column=Column(
            SQLEnum(
                JobStatus,
                name="job_status_enum",
                create_type=False,
                values_callable=lambda obj: [e.value for e in obj],
            ),
            nullable=False,
        ),
    )

    # When the worker may pick this row up. Stored in UTC; cron
    # next-fire is computed in the component's timezone before
    # conversion.
    scheduled_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    started_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    finished_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )

    attempt: int = Field(default=1, nullable=False)
    max_attempts: int = Field(default=3, nullable=False)

    error: str | None = Field(default=None, sa_column=Column(Text(), nullable=True))

    # Cross-link to the existing ``job`` table once ``simple_run_flow``
    # records the workflow run. ON DELETE SET NULL keeps trigger
    # history readable when an old workflow job row is purged.
    run_job_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            sa.Uuid(),
            ForeignKey("job.job_id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
    )

    created_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class TriggerJob(TriggerJobBase, table=True):  # type: ignore[call-arg]
    __tablename__ = "trigger_job"
    __table_args__ = (
        # Composite index used by the worker's claim query
        # (``WHERE status = 'queued' AND scheduled_at <= now()``).
        # Status comes first so the planner uses it as the equality
        # match and the scheduled_at range scan follows.
        sa.Index("ix_trigger_job_status_scheduled_at", "status", "scheduled_at"),
    )


# --------------------------------------------------------------------------- #
#  API schemas                                                                 #
# --------------------------------------------------------------------------- #


class TriggerJobRead(SQLModel):
    """Response shape for trigger-job history queries."""

    id: UUID
    flow_id: UUID
    component_id: str
    status: JobStatus
    scheduled_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    attempt: int
    max_attempts: int
    error: str | None
    run_job_id: UUID | None
    created_at: datetime

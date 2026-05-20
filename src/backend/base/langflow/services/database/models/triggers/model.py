"""Native trigger schedules and their queued executions.

Two tables back the trigger system:

* ``trigger`` — one row per schedule. Holds the cron expression, the
  target flow, the owning user, the timezone, and an ``is_active`` flag.
* ``trigger_job`` — the work queue. The worker claims rows from this
  table (``FOR UPDATE SKIP LOCKED`` on Postgres, an optimistic
  ``UPDATE ... WHERE status='queued'`` on SQLite) and dispatches them
  through ``simple_run_flow``. Each successful or terminally-failed
  job enqueues the next ``trigger_job`` for active cron triggers.

``trigger_job.status`` deliberately reuses :class:`JobStatus` from the
existing ``jobs`` model so the monitoring surface stays uniform with
the rest of the system. ``trigger_job.run_job_id`` is the cross-link
to the existing ``job`` table that records the actual graph execution.

See ``docs/triggers/01-DESIGN.md`` for the full RFC.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import JSON, Column, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from langflow.services.database.models.jobs.model import JobStatus

# JSONB on Postgres for indexability; plain JSON elsewhere (SQLite).
# Same variant pattern used by the ``job``, ``knowledge_base`` and
# ``memory_base`` tables.
JsonVariant = JSON().with_variant(JSONB(), "postgresql")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TriggerType(str, Enum):
    """Kind of trigger. ``CRON`` is the only value in v1.

    Listed as an enum from day one so adding ``POLL`` / ``STREAM`` in a
    later release is a non-breaking column-value addition.
    """

    CRON = "cron"


class TriggerBase(SQLModel):
    id: UUID = Field(default_factory=uuid4, primary_key=True)

    # Deleting a flow or a user removes all triggers that reference
    # them. The worker stops touching these rows automatically because
    # the cascade also removes the queued ``trigger_job`` rows.
    flow_id: UUID = Field(
        sa_column=Column(
            sa.Uuid(),
            ForeignKey("flow.id", ondelete="CASCADE"),
            index=True,
            nullable=False,
        ),
    )
    user_id: UUID = Field(
        sa_column=Column(
            sa.Uuid(),
            ForeignKey("user.id", ondelete="CASCADE"),
            index=True,
            nullable=False,
        ),
    )

    name: str = Field(nullable=False)

    trigger_type: TriggerType = Field(
        default=TriggerType.CRON,
        sa_column=Column(
            SQLEnum(
                TriggerType,
                name="trigger_type_enum",
                values_callable=lambda obj: [e.value for e in obj],
            ),
            nullable=False,
            index=True,
        ),
    )

    # Required when ``trigger_type == CRON``. Validated at the API
    # layer (croniter) before insertion.
    cron_expression: str | None = Field(default=None, nullable=True)

    # IANA timezone name. ``croniter`` plus ``zoneinfo`` compute the
    # next fire in this timezone before converting to UTC for storage.
    timezone: str = Field(default="UTC", nullable=False)

    # Optional default body forwarded to ``simple_run_flow`` as a
    # ``SimplifiedAPIRequest``-shaped dict. Free-form on purpose; the
    # API layer documents the expected keys.
    payload: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JsonVariant, nullable=True),
    )

    max_attempts: int = Field(default=3, nullable=False)
    is_active: bool = Field(default=True, nullable=False, index=True)

    created_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class Trigger(TriggerBase, table=True):  # type: ignore[call-arg]
    __tablename__ = "trigger"
    __table_args__ = (
        # A user picks the name; uniqueness scoped to that user mirrors
        # the convention used by ``flow.name``.
        UniqueConstraint("user_id", "name", name="uq_trigger_user_name"),
    )


class TriggerJobBase(SQLModel):
    id: UUID = Field(default_factory=uuid4, primary_key=True)

    trigger_id: UUID = Field(
        sa_column=Column(
            sa.Uuid(),
            ForeignKey("trigger.id", ondelete="CASCADE"),
            index=True,
            nullable=False,
        ),
    )

    # Reuse the existing ``job_status_enum`` Postgres type. The
    # ``create_type=False`` keeps Alembic from issuing a second
    # ``CREATE TYPE`` on Postgres deployments where the type already
    # exists (added by the original ``job`` migration). On SQLite the
    # column degrades to a checked string and the flag is a no-op.
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

    # When the worker may pick this row up. Stored in UTC; cron next-fire
    # computation happens in the trigger's timezone before conversion.
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
    # Snapshot of the trigger's max_attempts at enqueue time. Editing
    # the trigger later does not retroactively shorten an in-flight
    # retry chain.
    max_attempts: int = Field(default=3, nullable=False)

    error: str | None = Field(default=None, sa_column=Column(Text(), nullable=True))

    # Cross-link to the existing ``job`` table once ``simple_run_flow``
    # creates the workflow-run row. Nullable because it is only set
    # after dispatch starts. ON DELETE SET NULL keeps trigger history
    # readable if a workflow job row is purged.
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
        # Listed in this order so the planner can use it as a range
        # scan over ``scheduled_at`` once it filters on ``status``.
        sa.Index("ix_trigger_job_status_scheduled_at", "status", "scheduled_at"),
    )

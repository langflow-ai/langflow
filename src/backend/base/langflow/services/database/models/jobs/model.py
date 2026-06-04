from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, Column, DateTime, Integer, String, UniqueConstraint
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

# JSONB on Postgres for binary storage + GIN-indexable paths, JSON
# elsewhere (SQLite). Matches the variant used for other JSON columns
# on the ``ingestion_run`` and ``knowledge_base`` tables.
JsonVariant = JSON().with_variant(JSONB(), "postgresql")


class JobStatus(str, Enum):
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class JobType(str, Enum):
    """Enum to specify type of job.

    WORKFLOW: for workflow execution
    INGESTION: for knowledge base ingestion
    EVALUATION: for evaluation of workflows.

    Can be extended in future for other types of jobs.
    """

    WORKFLOW = "workflow"
    INGESTION = "ingestion"
    EVALUATION = "evaluation"


class JobBase(SQLModel):
    job_id: UUID = Field(primary_key=True, index=True)
    flow_id: UUID = Field(index=True)
    status: JobStatus = Field(
        default=JobStatus.QUEUED,
        sa_column=Column(
            SQLEnum(JobStatus, name="job_status_enum", values_callable=lambda obj: [item.value for item in obj]),
            nullable=False,
            index=False,
        ),
    )
    created_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    finished_timestamp: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    type: JobType | None = Field(
        default=JobType.WORKFLOW,
        sa_column=Column(
            SQLEnum(JobType, name="job_type_enum", values_callable=lambda obj: [item.value for item in obj]),
            nullable=True,
            index=True,
        ),
    )
    user_id: UUID | None = Field(index=True, nullable=True)
    asset_id: UUID | None = Field(index=True, nullable=True)
    asset_type: str | None = Field(
        index=False, nullable=True
    )  # Polymorphic: records if job is related to an entity like a KB, workflow, etc.
    dedupe_key: str | None = Field(
        index=True, nullable=True
    )  # Optional idempotency key to prevent duplicate jobs for the same asset and operation.

    # Free-form per-domain progress / outcome data. Populated by the
    # wrapped coroutine inside ``execute_with_status`` (e.g. KB
    # ingestion writes counters and per-item outcomes here as it runs).
    # Shape is intentionally untyped at this layer; each ``JobType``
    # owns the keys it writes. Nullable so existing rows stay readable
    # without a backfill — code reads with ``.get(...)``.
    job_metadata: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JsonVariant, nullable=True),
    )

    # Durable terminal payloads for background workflow runs. result holds
    # the final output blob on COMPLETED; error holds {type, message, ...}
    # on FAILED/TIMED_OUT. Both nullable so non-workflow jobs and in-flight
    # rows stay readable.
    result: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JsonVariant, nullable=True),
    )
    error: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JsonVariant, nullable=True),
    )


class Job(JobBase, table=True):  # type: ignore[call-arg]
    __tablename__ = "job"


class JobEvent(SQLModel, table=True):  # type: ignore[call-arg]
    """Durable event log for a background job.

    ``seq`` is the per-job monotonic cursor used as the SSE Last-Event-ID.
    UNIQUE(job_id, seq) enforces gap-free ordering and lets append_event
    detect collisions.
    """

    __tablename__ = "job_events"
    __table_args__ = (UniqueConstraint("job_id", "seq", name="uq_job_events_job_id_seq"),)

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    job_id: UUID = Field(index=True, nullable=False)
    seq: int = Field(sa_column=Column(Integer, nullable=False))
    event_type: str = Field(sa_column=Column(String, nullable=False))
    payload: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JsonVariant, nullable=True),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class SignalType(str, Enum):
    """Cooperative control signals delivered to a running job.

    Only STOP is implemented today; PAUSE/RESUME are intentionally left
    out of the enum until they're wired so we don't ship dead values.
    """

    STOP = "stop"


class ExecutionSignal(SQLModel, table=True):  # type: ignore[call-arg]
    """A control signal row for a job.

    The runner polls unconsumed rows at vertex boundaries and stamps
    ``consumed_at`` once acted upon.
    """

    __tablename__ = "execution_signals"

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    job_id: UUID = Field(index=True, nullable=False)
    signal_type: SignalType = Field(
        sa_column=Column(
            SQLEnum(
                SignalType,
                name="execution_signal_type_enum",
                values_callable=lambda obj: [item.value for item in obj],
            ),
            nullable=False,
        ),
    )
    data: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JsonVariant, nullable=True),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    consumed_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )

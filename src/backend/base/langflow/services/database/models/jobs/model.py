from datetime import datetime, timezone
from enum import Enum
from uuid import UUID

from sqlalchemy import Column, DateTime
from sqlalchemy import Enum as SQLEnum
from sqlmodel import Field, SQLModel


class JobStatus(str, Enum):
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class JobBase(SQLModel):
    job_id: UUID = Field(primary_key=True, index=True)
    flow_id: UUID = Field(index=True)
    status: JobStatus = Field(
        default=JobStatus.QUEUED,
        sa_column=Column(
            SQLEnum(JobStatus, name="job_status_enum", values_callable=lambda obj: [item.value for item in obj]),
            nullable=False,
            index=True,
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


class Job(JobBase, table=True):  # type: ignore[call-arg]
    __tablename__ = "job"

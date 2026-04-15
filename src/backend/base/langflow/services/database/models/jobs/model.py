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


class Job(JobBase, table=True):  # type: ignore[call-arg]
    __tablename__ = "job"

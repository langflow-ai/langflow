"""FlowSchedule model for scheduling automatic flow executions."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


class FlowScheduleBase(SQLModel):
    """Base model for flow schedules."""

    flow_id: UUID = Field(index=True, foreign_key="flow.id")
    is_active: bool = Field(default=False, nullable=False)
    schedule_type: str = Field(
        default="cron",
        nullable=False,
        description="Type of schedule: 'cron', 'interval'",
    )
    # Cron expression fields
    minute: str = Field(default="0", nullable=False, description="Cron minute field (0-59, */N, etc.)")
    hour: str = Field(default="*", nullable=False, description="Cron hour field (0-23, */N, etc.)")
    day_of_week: str = Field(default="*", nullable=False, description="Cron day of week (0-6, mon-sun, etc.)")
    day_of_month: str = Field(default="*", nullable=False, description="Cron day of month (1-31, */N, etc.)")
    month: str = Field(default="*", nullable=False, description="Cron month field (1-12, */N, etc.)")
    timezone: str = Field(default="UTC", nullable=False, description="Timezone for the schedule (IANA format)")
    start_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description="When the schedule becomes effective. None means immediately.",
    )
    # Metadata
    last_run_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    last_run_status: str | None = Field(default=None, nullable=True, description="Status of the last run")
    # Retry fields
    retry_count: int = Field(default=0, nullable=False, description="Current consecutive failure count, reset on success")
    max_retries: int = Field(default=3, nullable=False, description="Max retry attempts before marking as permanently failed")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class FlowSchedule(FlowScheduleBase, table=True):  # type: ignore[call-arg]
    """Database table for flow schedules."""

    __tablename__ = "flowschedule"

    id: UUID = Field(default_factory=uuid4, primary_key=True, unique=True)
    user_id: UUID = Field(index=True, foreign_key="user.id", nullable=False)

    __table_args__ = (UniqueConstraint("flow_id", name="unique_flow_schedule"),)


class FlowScheduleCreate(SQLModel):
    """Schema for creating a flow schedule."""

    flow_id: UUID
    is_active: bool = False
    schedule_type: str = "cron"
    minute: str = "0"
    hour: str = "*"
    day_of_week: str = "*"
    day_of_month: str = "*"
    month: str = "*"
    timezone: str = "UTC"
    start_at: datetime | None = None
    max_retries: int = 3


class FlowScheduleRead(FlowScheduleBase):
    """Schema for reading a flow schedule."""

    id: UUID
    user_id: UUID


class FlowScheduleUpdate(SQLModel):
    """Schema for updating a flow schedule."""

    is_active: bool | None = None
    schedule_type: str | None = None
    minute: str | None = None
    hour: str | None = None
    day_of_week: str | None = None
    day_of_month: str | None = None
    month: str | None = None
    timezone: str | None = None
    start_at: datetime | None = None
    max_retries: int | None = None

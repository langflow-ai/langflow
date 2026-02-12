from datetime import datetime, timezone
from uuid import UUID, uuid4

from pydantic import field_validator
from sqlalchemy import Column, DateTime, Text
from sqlmodel import JSON, Field, SQLModel


class FlowScheduleBase(SQLModel):
    """Base model for flow schedule configuration."""

    name: str | None = Field(default=None, nullable=True, description="Optional name for this schedule")
    is_active: bool = Field(default=True, description="Whether the schedule is active")
    cron_expression: str = Field(description="The cron expression (minute hour day_of_month month day_of_week)")
    timezone: str = Field(default="UTC", description="Timezone for the schedule (e.g. America/New_York)")
    days_of_week: list[int] | None = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
        description="Days of week to run (0=Monday, 6=Sunday). Used to build cron expression in UI.",
    )
    times_of_day: list[str] | None = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
        description="Times of day to run (HH:MM format). Used to build cron expression in UI.",
    )
    repeat_frequency: str | None = Field(
        default=None,
        nullable=True,
        description="Human-readable repeat frequency (e.g. 'daily', 'weekly', 'custom')",
    )

    @field_validator("cron_expression")
    @classmethod
    def validate_cron_expression(cls, v: str) -> str:
        parts = v.strip().split()
        if len(parts) != 5:
            msg = "Cron expression must have exactly 5 fields: minute hour day_of_month month day_of_week"
            raise ValueError(msg)
        return v.strip()

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        import zoneinfo

        try:
            zoneinfo.ZoneInfo(v)
        except (KeyError, zoneinfo.ZoneInfoNotFoundError):
            msg = f"Invalid timezone: {v}"
            raise ValueError(msg)
        return v


class FlowSchedule(FlowScheduleBase, table=True):  # type: ignore[call-arg]
    __tablename__ = "flow_schedule"

    id: UUID = Field(default_factory=uuid4, primary_key=True, unique=True)
    flow_id: UUID = Field(index=True, foreign_key="flow.id")
    user_id: UUID = Field(index=True, foreign_key="user.id")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    last_run_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    next_run_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    last_run_status: str | None = Field(default=None, nullable=True, description="Status of the last scheduled run")
    last_run_error: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True), description="Error from last run if failed"
    )


class FlowScheduleCreate(FlowScheduleBase):
    flow_id: UUID


class FlowScheduleUpdate(SQLModel):
    name: str | None = None
    is_active: bool | None = None
    cron_expression: str | None = None
    timezone: str | None = None
    days_of_week: list[int] | None = None
    times_of_day: list[str] | None = None
    repeat_frequency: str | None = None

    @field_validator("cron_expression")
    @classmethod
    def validate_cron_expression(cls, v: str | None) -> str | None:
        if v is None:
            return v
        parts = v.strip().split()
        if len(parts) != 5:
            msg = "Cron expression must have exactly 5 fields: minute hour day_of_month month day_of_week"
            raise ValueError(msg)
        return v.strip()

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str | None) -> str | None:
        if v is None:
            return v
        import zoneinfo

        try:
            zoneinfo.ZoneInfo(v)
        except (KeyError, zoneinfo.ZoneInfoNotFoundError):
            msg = f"Invalid timezone: {v}"
            raise ValueError(msg)
        return v


class FlowScheduleRead(FlowScheduleBase):
    id: UUID
    flow_id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    last_run_status: str | None = None
    last_run_error: str | None = None

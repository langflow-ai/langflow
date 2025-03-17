"""Scheduler database model."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from pydantic import Field
from sqlmodel import Column, DateTime, Field, Relationship, SQLModel, func

if TYPE_CHECKING:
    from langflow.services.database.models.flow import Flow


class SchedulerBase(SQLModel):
    """Base model for scheduler."""

    name: str = Field(index=True)
    description: str | None = Field(default=None)
    flow_id: UUID = Field(foreign_key="flow.id", index=True)
    cron_expression: str | None = Field(default=None)
    interval_seconds: int = Field(default=60)  # Default to 60 seconds
    enabled: bool = Field(default=True)
    last_run_at: datetime | None = Field(default=None)
    next_run_at: datetime | None = Field(default=None)


class Scheduler(SchedulerBase, table=True):  # type: ignore[call-arg]
    """Scheduler model."""

    __tablename__ = "scheduler"

    id: UUID | None = Field(
        default_factory=uuid4,
        primary_key=True,
        description="Unique ID for the scheduler",
    )
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=True),
        description="Creation time of the scheduler",
    )
    updated_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description="Last update time of the scheduler",
    )
    flow: "Flow" = Relationship(back_populates="schedulers")


class SchedulerCreate(SchedulerBase):
    """Create model for scheduler."""



class SchedulerRead(SchedulerBase):
    """Read model for scheduler."""

    id: UUID
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SchedulerUpdate(SQLModel):
    """Update model for scheduler."""

    name: str | None = None
    description: str | None = None
    cron_expression: str | None = None
    interval_seconds: int | None = None
    enabled: bool | None = None
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None

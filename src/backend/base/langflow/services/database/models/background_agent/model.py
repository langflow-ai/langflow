"""Database models for background agent execution."""

from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Optional
from uuid import UUID, uuid4

from pydantic import field_serializer, field_validator
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import Text, text
from sqlmodel import JSON, Column, Field, Relationship, SQLModel

if TYPE_CHECKING:
    from langflow.services.database.models.flow.model import Flow
    from langflow.services.database.models.user.model import User


class TriggerType(str, Enum):
    """Type of trigger for background agent execution."""

    CRON = "CRON"  # Cron schedule expression
    INTERVAL = "INTERVAL"  # Fixed interval (seconds)
    DATE = "DATE"  # One-time execution at specific date
    WEBHOOK = "WEBHOOK"  # Triggered by webhook/API call
    EVENT = "EVENT"  # Triggered by system events


class AgentStatus(str, Enum):
    """Status of background agent."""

    ACTIVE = "ACTIVE"  # Agent is running
    PAUSED = "PAUSED"  # Agent is paused
    STOPPED = "STOPPED"  # Agent is stopped
    ERROR = "ERROR"  # Agent encountered error


class BackgroundAgentBase(SQLModel):
    """Base model for background agent configuration."""

    # Suppress warnings during migrations
    __mapper_args__ = {"confirm_deleted_rows": False}

    name: str = Field(index=True, description="Name of the background agent")
    description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    flow_id: UUID = Field(foreign_key="flow.id", index=True, description="Associated flow ID")
    trigger_type: TriggerType = Field(
        sa_column=Column(
            SQLEnum(
                TriggerType,
                name="trigger_type_enum",
                values_callable=lambda enum: [member.value for member in enum],
            ),
            nullable=False,
        ),
        description="Type of trigger for execution",
    )
    trigger_config: dict = Field(
        default={},
        sa_column=Column(JSON),
        description="Configuration for the trigger (cron expression, interval, etc.)",
    )
    input_config: dict = Field(
        default={},
        sa_column=Column(JSON),
        description="Input configuration for flow execution",
    )
    status: AgentStatus = Field(
        default=AgentStatus.STOPPED,
        sa_column=Column(
            SQLEnum(
                AgentStatus,
                name="agent_status_enum",
                values_callable=lambda enum: [member.value for member in enum],
            ),
            nullable=False,
            server_default=text("'STOPPED'"),
        ),
        description="Current status of the agent",
    )
    enabled: bool = Field(default=True, description="Whether the agent is enabled")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    last_run_at: datetime | None = Field(default=None, nullable=True)
    next_run_at: datetime | None = Field(default=None, nullable=True)

    @field_serializer("created_at", "updated_at", "last_run_at", "next_run_at")
    def serialize_datetime(self, value):
        if isinstance(value, datetime):
            value = value.replace(microsecond=0)
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            return value.isoformat()
        return value

    @field_validator("created_at", "updated_at", "last_run_at", "next_run_at", mode="before")
    @classmethod
    def validate_dt(cls, v):
        if v is None:
            return v
        if isinstance(v, datetime):
            return v
        return datetime.fromisoformat(v)


class BackgroundAgent(BackgroundAgentBase, table=True):  # type: ignore[call-arg]
    """Database model for background agent."""

    id: UUID = Field(default_factory=uuid4, primary_key=True, unique=True)
    user_id: UUID = Field(index=True, foreign_key="user.id")
    user: "User" = Relationship()
    flow: "Flow" = Relationship()
    executions: list["BackgroundAgentExecution"] = Relationship(back_populates="agent")


class BackgroundAgentCreate(SQLModel):
    """Schema for creating a background agent."""

    name: str
    description: str | None = None
    flow_id: UUID
    trigger_type: TriggerType
    trigger_config: dict = {}
    input_config: dict = {}
    enabled: bool = True


class BackgroundAgentRead(BackgroundAgentBase):
    """Schema for reading a background agent."""

    id: UUID
    user_id: UUID


class BackgroundAgentUpdate(SQLModel):
    """Schema for updating a background agent."""

    name: str | None = None
    description: str | None = None
    trigger_type: TriggerType | None = None
    trigger_config: dict | None = None
    input_config: dict | None = None
    status: AgentStatus | None = None
    enabled: bool | None = None


class BackgroundAgentExecutionBase(SQLModel):
    """Base model for background agent execution history."""

    # Suppress warnings during migrations
    __mapper_args__ = {"confirm_deleted_rows": False}

    agent_id: UUID = Field(foreign_key="backgroundagent.id", index=True)
    started_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    completed_at: datetime | None = Field(default=None, nullable=True)
    status: str = Field(
        default="RUNNING",
        description="Execution status: RUNNING, SUCCESS, FAILED",
    )
    error_message: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    result: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    trigger_source: str | None = Field(
        default=None,
        description="What triggered this execution (scheduled, webhook, manual, etc.)",
    )

    @field_serializer("started_at", "completed_at")
    def serialize_datetime(self, value):
        if isinstance(value, datetime):
            value = value.replace(microsecond=0)
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            return value.isoformat()
        return value

    @field_validator("started_at", "completed_at", mode="before")
    @classmethod
    def validate_dt(cls, v):
        if v is None:
            return v
        if isinstance(v, datetime):
            return v
        return datetime.fromisoformat(v)


class BackgroundAgentExecution(BackgroundAgentExecutionBase, table=True):  # type: ignore[call-arg]
    """Database model for background agent execution history."""

    id: UUID = Field(default_factory=uuid4, primary_key=True, unique=True)
    agent: Optional["BackgroundAgent"] = Relationship(back_populates="executions")


class BackgroundAgentExecutionCreate(SQLModel):
    """Schema for creating an execution record."""

    agent_id: UUID
    trigger_source: str | None = None


class BackgroundAgentExecutionRead(BackgroundAgentExecutionBase):
    """Schema for reading an execution record."""

    id: UUID

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

JsonVariant = JSON().with_variant(JSONB(), "postgresql")


class MCPJobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


_TERMINAL_STATUSES = frozenset({MCPJobStatus.COMPLETED, MCPJobStatus.FAILED, MCPJobStatus.CANCELLED})


class MCPJobBase(SQLModel):
    """Persistent record of an MCP tool invocation that runs in the job queue.

    Created when ``handle_call_tool`` sees a flow with ``long_running=True``;
    a worker drains pending rows and updates ``status``/``progress``/``result``
    until terminal. See ``docs/docs/Agents/mcp-catalog-and-long-running.mdx``.
    """

    # FKs use sa_column so we can pin ondelete behavior — SQLModel's
    # ``foreign_key=`` shortcut creates anonymous FKs without ondelete, which
    # the autogenerate check flags as a phantom diff against the migration.
    project_id: UUID = Field(
        sa_column=Column(
            Uuid(),
            ForeignKey("folder.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
    )
    flow_id: UUID = Field(
        sa_column=Column(
            Uuid(),
            ForeignKey("flow.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
    )
    tool_name: str = Field(max_length=255, nullable=False)
    inputs: dict[str, Any] = Field(sa_column=Column(JsonVariant, nullable=False))
    status: MCPJobStatus = Field(
        default=MCPJobStatus.PENDING,
        sa_column=Column(
            # Stored as VARCHAR rather than a DB enum so adding a future state
            # (e.g. ``timed_out``) doesn't require an Alembic enum-alter.
            "status",
            Text(),
            nullable=False,
            server_default=MCPJobStatus.PENDING.value,
            index=True,
        ),
    )
    progress: int = Field(default=0, nullable=False)
    result: dict[str, Any] | None = Field(default=None, sa_column=Column(JsonVariant, nullable=True))
    error: str | None = Field(default=None, sa_column=Column(Text(), nullable=True))
    callback_url: str | None = Field(default=None, max_length=2048, nullable=True)
    created_by: UUID | None = Field(
        default=None,
        sa_column=Column(
            Uuid(),
            ForeignKey("user.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    completed_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )

    @property
    def is_terminal(self) -> bool:
        return self.status in _TERMINAL_STATUSES


class MCPJob(MCPJobBase, table=True):  # type: ignore[call-arg]
    __tablename__ = "mcp_jobs"

    id: UUID = Field(default_factory=uuid4, primary_key=True, nullable=False)


class MCPJobCreate(SQLModel):
    flow_id: UUID
    inputs: dict[str, Any]
    callback_url: str | None = None


class MCPJobRead(SQLModel):
    id: UUID
    project_id: UUID
    flow_id: UUID
    tool_name: str
    status: MCPJobStatus
    progress: int
    result: dict[str, Any] | None
    error: str | None
    callback_url: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, Index, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


class SessionMemoryStateTable(SQLModel, table=True):  # type: ignore[call-arg]
    """Rolling summary of the messages older than an Agent's chat-history window.

    One row per (flow, message owner, session, context). ``flow_id`` and ``user_id`` carry no FK:
    they mirror the message scoping and rows are removed explicitly with the session or flow.
    ``version`` is the compare-and-swap token for concurrent runs.
    """

    __tablename__ = "session_memory_state"
    __table_args__ = (
        UniqueConstraint("flow_id", "user_id", "session_id", "context_id", name="uq_session_memory_state_scope"),
        Index("ix_session_memory_state_flow_session", "flow_id", "session_id"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    flow_id: UUID
    user_id: UUID
    session_id: str
    context_id: str = Field(default="")
    summary: str = Field(default="", sa_column=Column(Text, nullable=False, server_default=""))
    cursor_message_id: UUID | None = Field(default=None)
    cursor_timestamp: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    folded_count: int = Field(default=0)
    summary_model: str | None = Field(default=None)
    version: int = Field(default=0)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

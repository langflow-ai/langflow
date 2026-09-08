from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel
from sqlalchemy import Column, DateTime, ForeignKey, Index, func
from sqlmodel import JSON, Field, SQLModel


class FlowAuditEntry(SQLModel, table=True):  # type: ignore[call-arg]
    """One person's editing session on one flow, and what it changed.

    Not a version: it carries a description of the change, never a graph, so it
    cannot be restored from and does not grow with the size of the flow. Not an
    authorization row either — that log answers whether an action was allowed,
    this one answers what the action did.
    """

    __tablename__ = "flow_audit_entry"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    flow_id: UUID = Field(
        sa_column=Column(ForeignKey("flow.id", ondelete="CASCADE"), index=True, nullable=False),
    )
    user_id: UUID | None = Field(
        sa_column=Column(ForeignKey("user.id", ondelete="SET NULL"), index=True, nullable=True),
    )
    source: str = Field(nullable=False, max_length=32)
    from_version_token: UUID | None = Field(default=None, nullable=True)
    to_version_token: UUID | None = Field(default=None, nullable=True)
    changes: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    started_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )

    # The read path is always "this flow, newest first", and coalescing looks up
    # the open entry by (flow, actor) ordered the same way.
    __table_args__ = (
        Index("ix_flow_audit_entry_flow_updated", "flow_id", "updated_at"),
        Index("ix_flow_audit_entry_flow_user_updated", "flow_id", "user_id", "updated_at"),
    )


class FlowAuditEntryRead(BaseModel):
    id: UUID
    flow_id: UUID
    user_id: UUID | None
    username: str | None = None
    source: str
    # The versions this write moved between. Not version-history ids — those are
    # separate snapshots. These are the concurrency stamp, so a reader can line an
    # entry up with the 409 somebody was given, whose body carries the same pair.
    from_version_token: UUID | None = None
    to_version_token: UUID | None = None
    changes: list
    started_at: datetime | None
    updated_at: datetime | None


class FlowAuditListResponse(BaseModel):
    entries: list[FlowAuditEntryRead]
    next_cursor: str | None = None

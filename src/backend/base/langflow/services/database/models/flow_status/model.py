"""Flow Status database model for approval workflow status tracking."""

from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Column, DateTime, String, Text
from sqlmodel import Field, SQLModel


class FlowStatusEnum(str, Enum):
    """Enum for flow status values."""

    DRAFT = "Draft"
    SUBMITTED = "Submitted"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    PUBLISHED = "Published"
    UNPUBLISHED = "Unpublished"
    DELETED = "Deleted"


class FlowStatusBase(SQLModel):
    """Base model for flow status."""

    status_name: str = Field(
        sa_column=Column(String(50), nullable=False, unique=True, index=True)
    )
    description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))


class FlowStatus(FlowStatusBase, table=True):  # type: ignore[call-arg]
    """Flow Status lookup table model."""

    __tablename__ = "flow_status"

    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class FlowStatusRead(FlowStatusBase):
    """Schema for reading a flow status."""

    id: int
    created_at: datetime

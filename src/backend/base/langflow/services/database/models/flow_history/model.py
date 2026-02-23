from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, field_serializer
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import UniqueConstraint, text
from sqlmodel import JSON, Column, Field, SQLModel


class FlowStateEnum(str, Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class FlowHistory(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "flow_history"
    __mapper_args__ = {"confirm_deleted_rows": False}

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    flow_id: UUID = Field(index=True, foreign_key="flow.id")
    user_id: UUID = Field(index=True, foreign_key="user.id")
    data: dict | None = Field(default=None, sa_column=Column(JSON))
    state: FlowStateEnum = Field(
        default=FlowStateEnum.DRAFT,
        sa_column=Column(
            SQLEnum(
                FlowStateEnum,
                name="flow_state_enum",
                values_callable=lambda enum: [member.value for member in enum],
            ),
            nullable=False,
            server_default=text("'DRAFT'"),
        ),
    )
    version_number: int = Field(nullable=False)
    description: str | None = Field(default=None, nullable=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)

    @property
    def version_tag(self) -> str:
        return f"v{self.version_number}"

    __table_args__ = (UniqueConstraint("flow_id", "version_number", name="unique_flow_version_number"),)


class FlowHistoryRead(BaseModel):
    """Schema for listing history entries — excludes data for performance."""

    id: UUID
    flow_id: UUID
    user_id: UUID
    state: FlowStateEnum
    version_number: int
    version_tag: str
    description: str | None
    created_at: datetime

    @field_serializer("created_at")
    def serialize_datetime(self, value: datetime) -> str:
        if isinstance(value, datetime):
            value = value.replace(microsecond=0)
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            return value.isoformat()
        return value


class FlowHistoryReadFull(FlowHistoryRead):
    """Schema for a single history entry — includes full data."""

    data: dict | None


class FlowHistoryCreate(BaseModel):
    """Schema for creating a history entry — user only provides description."""

    description: str | None = None

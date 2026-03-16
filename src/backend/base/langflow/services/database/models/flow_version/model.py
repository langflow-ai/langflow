from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from pydantic import BaseModel, computed_field, field_serializer
from pydantic import Field as PydanticField
from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, UniqueConstraint, func
from sqlmodel import JSON, Field, SQLModel


class FlowVersion(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "flow_version"
    __mapper_args__ = {"confirm_deleted_rows": False}

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    flow_id: UUID = Field(
        sa_column=Column(ForeignKey("flow.id", ondelete="CASCADE"), index=True, nullable=False),
    )
    user_id: UUID | None = Field(
        sa_column=Column(ForeignKey("user.id", ondelete="SET NULL"), index=True, nullable=True),
    )
    data: dict | None = Field(default=None, sa_column=Column(JSON))
    version_number: int = Field(nullable=False, ge=1)
    description: str | None = Field(default=None, nullable=True, max_length=500)
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True),
    )

    # The UniqueConstraint on (flow_id, version_number) creates an implicit composite
    # btree index that also covers ORDER BY version_number DESC queries filtered by
    # flow_id. No additional index is needed for the list/prune queries.
    __table_args__ = (
        UniqueConstraint("flow_id", "version_number", name="unique_flow_version_number"),
        CheckConstraint("version_number >= 1", name="check_version_number_positive"),
    )


class FlowVersionRead(BaseModel):
    """Schema for listing flow versions — excludes data for performance."""

    id: UUID
    flow_id: UUID
    user_id: UUID | None
    version_number: int = PydanticField(ge=1)
    description: str | None
    created_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def version_tag(self) -> str:
        return f"v{self.version_number}"

    @field_serializer("created_at")
    def serialize_datetime(self, value: datetime) -> str:
        value = value.replace(microsecond=0)
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()


class FlowVersionReadWithData(FlowVersionRead):
    """Schema for a single flow version — includes full data."""

    data: dict | None


class FlowVersionCreate(BaseModel):
    """Schema for creating a flow version — user only provides description."""

    description: str | None = Field(default=None, max_length=500)


class FlowVersionListResponse(BaseModel):
    """Wrapper for the list endpoint — includes flow versions and the configured max."""

    entries: list[FlowVersionRead]
    max_entries: int = PydanticField(ge=1)

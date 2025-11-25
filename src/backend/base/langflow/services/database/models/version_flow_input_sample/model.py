"""Version Flow Input Sample database model for storing sample inputs and outputs."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlmodel import JSON, Field, Relationship, SQLModel

if TYPE_CHECKING:
    from langflow.services.database.models.flow_version.model import FlowVersion


class VersionFlowInputSampleBase(SQLModel):
    """Base model for version flow input samples."""

    version: str = Field(sa_column=Column(String(50), nullable=False))
    storage_account: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    container_name: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    file_names: list[str] | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    sample_text: list[str] | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    sample_output: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))


class VersionFlowInputSample(VersionFlowInputSampleBase, table=True):  # type: ignore[call-arg]
    """Version Flow Input Sample table model."""

    __tablename__ = "version_flow_input_sample"

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    # Flow version relationship with CASCADE delete
    flow_version_id: UUID = Field(
        sa_column=Column(
            PGUUID(as_uuid=True),
            ForeignKey("flow_version.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )

    # Original flow reference for quick lookup
    original_flow_id: UUID = Field(
        sa_column=Column(
            PGUUID(as_uuid=True),
            ForeignKey("flow.id"),
            nullable=False,
            index=True,
        )
    )

    # Timestamps
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    # Relationships
    flow_version: Optional["FlowVersion"] = Relationship(
        back_populates="input_sample",
        sa_relationship_kwargs={
            "foreign_keys": "VersionFlowInputSample.flow_version_id",
        },
    )


class VersionFlowInputSampleCreate(SQLModel):
    """Schema for creating a version flow input sample."""

    version: str
    original_flow_id: UUID
    storage_account: str | None = None
    container_name: str | None = None
    file_names: list[str] | None = None
    sample_text: list[str] | None = None
    sample_output: dict | None = None


class VersionFlowInputSampleRead(VersionFlowInputSampleBase):
    """Schema for reading a version flow input sample."""

    id: UUID
    flow_version_id: UUID
    original_flow_id: UUID
    created_at: datetime
    updated_at: datetime

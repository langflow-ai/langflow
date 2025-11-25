"""Flow Version database model for approval workflow versioning."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, String, Text, UniqueConstraint
from sqlmodel import JSON, Field, Relationship, SQLModel

if TYPE_CHECKING:
    from langflow.services.database.models.flow.model import Flow
    from langflow.services.database.models.flow_status.model import FlowStatus
    from langflow.services.database.models.user.model import User
    from langflow.services.database.models.version_flow_input_sample.model import VersionFlowInputSample


class FlowVersionBase(SQLModel):
    """Base model for flow versions."""

    version: str = Field(sa_column=Column(String(50), nullable=False))
    title: str | None = Field(default=None, sa_column=Column(String(255), nullable=True))
    description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    tags: list[str] | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    agent_logo: str | None = Field(default=None, sa_column=Column(String(1000), nullable=True))


class FlowVersion(FlowVersionBase, table=True):  # type: ignore[call-arg]
    """
    Flow Version table model for approval workflow.

    Tracks all versions of flows submitted for approval with complete metadata.
    Each submission creates a new version entry with a cloned flow snapshot.
    """

    __tablename__ = "flow_version"

    # Primary key
    id: UUID = Field(default_factory=uuid4, primary_key=True)

    # Flow relationships
    original_flow_id: UUID = Field(
        foreign_key="flow.id",
        nullable=False,
        index=True,
    )
    version_flow_id: UUID | None = Field(
        default=None,
        foreign_key="flow.id",
        nullable=True,
        index=True,
    )

    # Status relationship
    status_id: int = Field(
        foreign_key="flow_status.id",
        nullable=False,
        index=True,
    )

    # Sample input relationship (nullable - FK added via migration)
    sample_id: UUID | None = Field(
        default=None,
        nullable=True,
    )

    # Submission audit fields
    submitted_by: UUID | None = Field(
        default=None,
        foreign_key="user.id",
        nullable=True,
        index=True,
    )
    submitted_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )

    # Submission name and email (from Keycloak token)
    submitted_by_name: str | None = Field(
        default=None,
        sa_column=Column(String(255), nullable=True),
    )
    submitted_by_email: str | None = Field(
        default=None,
        sa_column=Column(String(255), nullable=True),
    )

    # Review audit fields
    reviewed_by: UUID | None = Field(
        default=None,
        foreign_key="user.id",
        nullable=True,
    )
    reviewed_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    reviewed_by_name: str | None = Field(
        default=None,
        sa_column=Column(String(255), nullable=True),
    )
    reviewed_by_email: str | None = Field(
        default=None,
        sa_column=Column(String(255), nullable=True),
    )
    rejection_reason: str | None = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
    )

    # Publish audit fields
    published_by: UUID | None = Field(
        default=None,
        foreign_key="user.id",
        nullable=True,
    )
    published_by_name: str | None = Field(
        default=None,
        sa_column=Column(String(255), nullable=True),
    )
    published_by_email: str | None = Field(
        default=None,
        sa_column=Column(String(255), nullable=True),
    )
    published_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )

    # Standard audit fields
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    # Relationships
    original_flow: Optional["Flow"] = Relationship(
        sa_relationship_kwargs={"foreign_keys": "FlowVersion.original_flow_id"}
    )
    version_flow: Optional["Flow"] = Relationship(
        sa_relationship_kwargs={"foreign_keys": "FlowVersion.version_flow_id"}
    )
    status: Optional["FlowStatus"] = Relationship()
    submitter: Optional["User"] = Relationship(
        sa_relationship_kwargs={"foreign_keys": "FlowVersion.submitted_by"}
    )
    reviewer: Optional["User"] = Relationship(
        sa_relationship_kwargs={"foreign_keys": "FlowVersion.reviewed_by"}
    )
    publisher: Optional["User"] = Relationship(
        sa_relationship_kwargs={"foreign_keys": "FlowVersion.published_by"}
    )
    input_sample: Optional["VersionFlowInputSample"] = Relationship(
        back_populates="flow_version",
        sa_relationship_kwargs={
            "foreign_keys": "VersionFlowInputSample.flow_version_id",
            "uselist": False,
        },
    )

    # Table constraints
    __table_args__ = (
        # Unique constraint: version must be unique per original flow
        UniqueConstraint("original_flow_id", "version", name="uq_flow_version_original_flow_version"),
    )


class FlowVersionCreate(SQLModel):
    """Schema for creating a flow version (submit for approval)."""

    title: str
    version: str
    description: str | None = None
    tags: list[str] | None = None
    agent_logo: str | None = None
    # Sample input fields
    storage_account: str | None = None
    container_name: str | None = None
    file_names: list[str] | None = None
    sample_text: list[str] | None = None
    sample_output: dict | None = None


class FlowVersionRead(FlowVersionBase):
    """Schema for reading a flow version."""

    id: UUID
    original_flow_id: UUID
    version_flow_id: UUID | None
    status_id: int
    sample_id: UUID | None
    # Submission fields
    submitted_by: UUID | None
    submitted_by_name: str | None = None
    submitted_by_email: str | None = None
    submitted_at: datetime | None
    # Review fields
    reviewed_by: UUID | None
    reviewed_by_name: str | None = None
    reviewed_by_email: str | None = None
    reviewed_at: datetime | None
    rejection_reason: str | None
    # Publish fields
    published_by: UUID | None = None
    published_by_name: str | None = None
    published_by_email: str | None = None
    published_at: datetime | None = None
    # Standard fields
    created_at: datetime
    updated_at: datetime
    # Additional fields from joins (for backward compatibility)
    status_name: str | None = None
    submitter_name: str | None = None  # Alias for submitted_by_name
    submitter_email: str | None = None
    reviewer_name: str | None = None  # Alias for reviewed_by_name
    flow_data: dict | None = None  # Flow data from cloned flow for visualization
    organization_name: str | None = None


class FlowVersionUpdate(SQLModel):
    """Schema for updating a flow version."""

    title: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    agent_logo: str | None = None


class FlowVersionRejectRequest(SQLModel):
    """Schema for rejecting a flow version."""

    rejection_reason: str | None = None


# Rebuild Pydantic models to resolve forward references
FlowVersionRead.model_rebuild()

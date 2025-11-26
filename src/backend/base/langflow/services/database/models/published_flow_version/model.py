"""Published Flow Version database model for marketplace versioning."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import Column, Index, Text, UniqueConstraint
from sqlmodel import JSON, DateTime, Field, Relationship, SQLModel, func

if TYPE_CHECKING:
    from langflow.services.database.models.flow.model import Flow
    from langflow.services.database.models.published_flow.model import PublishedFlow
    from langflow.services.database.models.user.model import User


class PublishedFlowVersionBase(SQLModel):
    """Base model for published flow versions."""

    version: str = Field(max_length=50, nullable=False)
    flow_name: str = Field(max_length=255, nullable=False)
    flow_icon: str | None = Field(default=None, nullable=True, max_length=1000)
    description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    tags: list[str] | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    active: bool = Field(default=True, nullable=False)
    drafted: bool = Field(default=False, nullable=False, description="Version currently loaded in editor")
    published_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    )


class PublishedFlowVersion(PublishedFlowVersionBase, table=True):  # type: ignore[call-arg]
    """
    Published Flow Version table model.

    Tracks all versions of published flows with complete metadata snapshots.
    Each publish creates a new version entry with independent cloned flow data.

    Example:
        Flow F1 published 3 times creates 3 records:
        - id=1, version="v1", active=False
        - id=2, version="v2", active=False
        - id=3, version="v3", active=True
    """

    __tablename__ = "published_flow_version"

    # Primary key - auto-increment integer
    id: int | None = Field(default=None, primary_key=True)

    # Flow relationships
    flow_id_cloned_to: UUID = Field(
        foreign_key="flow.id",
        nullable=False,
        description="The cloned flow created for this version",
    )
    flow_id_cloned_from: UUID = Field(
        foreign_key="flow.id",
        nullable=False,
        description="The original flow this version was cloned from",
    )
    published_flow_id: UUID = Field(
        foreign_key="published_flow.id",
        nullable=False,
        description="Reference to the published_flow record",
    )

    # Audit fields
    published_by: UUID = Field(foreign_key="user.id", nullable=False)
    created_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    )

    # Table constraints and indexes
    __table_args__ = (
        # Unique constraint: version must be unique per original flow
        UniqueConstraint("flow_id_cloned_from", "version", name="uq_published_flow_version_flow_id_cloned_from_version"),
        # Partial unique index: ensures only one active version per published flow
        Index(
            "uq_published_flow_version_one_active",
            "published_flow_id",
            "active",
            unique=True,
            postgresql_where=Column("active") == True,  # noqa: E712
        ),
        # Partial unique index: ensures only one drafted version per original flow
        Index(
            "uq_published_flow_version_one_drafted",
            "flow_id_cloned_from",
            "drafted",
            unique=True,
            postgresql_where=Column("drafted") == True,  # noqa: E712
        ),
    )

    # Relationships
    published_flow: Optional["PublishedFlow"] = Relationship(back_populates="versions")
    cloned_flow: Optional["Flow"] = Relationship(
        sa_relationship_kwargs={"foreign_keys": "PublishedFlowVersion.flow_id_cloned_to"}
    )
    original_flow: Optional["Flow"] = Relationship(
        sa_relationship_kwargs={"foreign_keys": "PublishedFlowVersion.flow_id_cloned_from"}
    )
    publisher: Optional["User"] = Relationship()


class PublishedFlowVersionRead(PublishedFlowVersionBase):
    """Schema for reading published flow version."""

    id: int | str  # int for published_flow_version, str (UUID) for flow_version
    flow_id_cloned_to: UUID | None
    flow_id_cloned_from: UUID
    published_flow_id: UUID | None
    published_by: UUID
    created_at: datetime
    drafted: bool
    status_name: str | None = None  # Status from flow_status table (when using flow_version)


class RevertToVersionResponse(SQLModel):
    """Response schema for reverting to a version."""

    message: str
    version: str
    flow_id: UUID
    cloned_flow_id: UUID

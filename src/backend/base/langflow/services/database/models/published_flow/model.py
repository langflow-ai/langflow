"""Published Flow database model for marketplace functionality."""

from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Optional
from uuid import UUID, uuid4

from sqlalchemy import Column, Text, UniqueConstraint, text
from sqlalchemy import Enum as SQLEnum
from sqlmodel import JSON, Field, Relationship, SQLModel

if TYPE_CHECKING:
    from langflow.services.database.models.flow.model import Flow
    from langflow.services.database.models.user.model import User


class PublishStatusEnum(str, Enum):
    """Enum for published flow status."""

    PUBLISHED = "PUBLISHED"
    UNPUBLISHED = "UNPUBLISHED"


class PublishedFlowBase(SQLModel):
    """Base model for published flows."""

    status: PublishStatusEnum = Field(
        default=PublishStatusEnum.PUBLISHED,
        sa_column=Column(
            SQLEnum(
                PublishStatusEnum,
                name="publish_status_enum",
                values_callable=lambda enum: [member.value for member in enum],
                create_constraint=True,
            ),
            nullable=False,
            server_default=text("'PUBLISHED'"),
            index=True,
        ),
    )
    version: str | None = Field(default=None, nullable=True, max_length=50)
    description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    tags: list[str] | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    category: str | None = Field(default=None, nullable=True, max_length=100, index=True)
    flow_data: dict | None = Field(default=None, sa_column=Column(JSON, nullable=False))
    published_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
    unpublished_at: datetime | None = Field(default=None, nullable=True)


class PublishedFlow(PublishedFlowBase, table=True):  # type: ignore[call-arg]
    """Published Flow table model."""

    __tablename__ = "published_flow"  # Explicit table name with underscore

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    flow_id: UUID = Field(foreign_key="flow.id", nullable=False, index=True)
    user_id: UUID = Field(foreign_key="user.id", nullable=False, index=True)
    published_by: UUID = Field(foreign_key="user.id", nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Relationships
    flow: Optional["Flow"] = Relationship()
    user: Optional["User"] = Relationship(
        sa_relationship_kwargs={"foreign_keys": "PublishedFlow.user_id", "lazy": "joined"}
    )
    publisher: Optional["User"] = Relationship(
        sa_relationship_kwargs={"foreign_keys": "PublishedFlow.published_by", "lazy": "joined"}
    )

    __table_args__ = (UniqueConstraint("flow_id", name="uq_published_flow_flow_id"),)


class PublishedFlowCreate(SQLModel):
    """Schema for creating a published flow."""

    version: str | None = None
    category: str | None = None


class PublishedFlowRead(PublishedFlowBase):
    """Schema for reading a published flow."""

    id: UUID
    flow_id: UUID
    user_id: UUID
    published_by: UUID
    created_at: datetime
    updated_at: datetime
    # Additional fields from joins
    flow_name: str | None = None
    flow_icon: str | None = None
    published_by_username: str | None = None


class PublishedFlowUpdate(SQLModel):
    """Schema for updating a published flow."""

    version: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    category: str | None = None

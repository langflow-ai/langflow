from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from pydantic import field_serializer, field_validator
from sqlmodel import JSON, Column, Field, Relationship, SQLModel

from langflow.serialization.serialization import serialize

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.database.models.actor.model import Actor
    from langflow.services.database.models.flow.model import Flow
    from langflow.services.database.models.user.model import User


class TaskBase(SQLModel):
    """Base model for Task containing common fields without relationships."""

    title: str
    description: str
    attachments: list[str] = Field(sa_column=Column(JSON))
    category: str
    state: str
    status: str
    result: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    input_request: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    cron_expression: str | None = Field(default=None)

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def validate_datetime(cls, v):
        if isinstance(v, datetime):
            return v
        return datetime.fromisoformat(v)

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        valid_statuses = ["pending", "running", "completed", "failed", "canceled", "processing"]
        if v not in valid_statuses:
            msg = f"Invalid status: {v}. Must be one of {valid_statuses}"
            raise ValueError(msg)
        return v


class Task(TaskBase, table=True):  # type: ignore[call-arg]
    """Task table model with foreign key relationships."""

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    # Foreign keys are defined in the table class, not the base class
    author_id: UUID = Field(foreign_key="actor.id", index=True)
    assignee_id: UUID = Field(foreign_key="actor.id", index=True)

    # Relationship definitions
    author: Actor = Relationship(
        back_populates="authored_tasks",
        sa_relationship_kwargs={"primaryjoin": "Task.author_id==Actor.id", "foreign_keys": "Task.author_id"},
    )
    assignee: Actor = Relationship(
        back_populates="assigned_tasks",
        sa_relationship_kwargs={"primaryjoin": "Task.assignee_id==Actor.id", "foreign_keys": "Task.assignee_id"},
    )

    async def get_author_entity(self, session: AsyncSession) -> User | Flow | None:
        """Get the actual User or Flow that is the author of this task."""
        return await self.author.get_entity(session)

    async def get_assignee_entity(self, session: AsyncSession) -> User | Flow | None:
        """Get the actual User or Flow that is the assignee of this task."""
        return await self.assignee.get_entity(session)


class TaskCreate(SQLModel):
    title: str
    description: str
    attachments: list[str] = Field(default_factory=list)
    author_id: UUID | None = None
    assignee_id: UUID | None = None
    user_author_id: UUID | None = None
    flow_author_id: UUID | None = None
    user_assignee_id: UUID | None = None
    flow_assignee_id: UUID | None = None
    category: str
    state: str
    status: str = "pending"
    cron_expression: str | None = None

    @field_validator("author_id")
    @classmethod
    def validate_author_id(cls, v, values):
        """Ensure that either author_id OR one of user_author_id/flow_author_id is provided."""
        user_author_id = values.data.get("user_author_id")
        flow_author_id = values.data.get("flow_author_id")

        if v is None and user_author_id is None and flow_author_id is None:
            msg = "Must provide either author_id, user_author_id, or flow_author_id"
            raise ValueError(msg)

        if v is not None and (user_author_id is not None or flow_author_id is not None):
            msg = "Cannot provide both author_id and user_author_id/flow_author_id"
            raise ValueError(msg)

        return v

    @field_validator("assignee_id")
    @classmethod
    def validate_assignee_id(cls, v, values):
        """Ensure that either assignee_id OR one of user_assignee_id/flow_assignee_id is provided."""
        user_assignee_id = values.data.get("user_assignee_id")
        flow_assignee_id = values.data.get("flow_assignee_id")

        if v is None and user_assignee_id is None and flow_assignee_id is None:
            msg = "Must provide either assignee_id, user_assignee_id, or flow_assignee_id"
            raise ValueError(msg)

        if v is not None and (user_assignee_id is not None or flow_assignee_id is not None):
            msg = "Cannot provide both assignee_id and user_assignee_id/flow_assignee_id"
            raise ValueError(msg)

        return v


class TaskRead(TaskBase):
    id: UUID
    author_id: UUID
    assignee_id: UUID

    @field_serializer("result")
    @classmethod
    def serialize_result(cls, v):
        return serialize(v)


class TaskUpdate(SQLModel):
    title: str | None = None
    description: str | None = None
    attachments: list[str] | None = None
    author_id: UUID | None = None
    assignee_id: UUID | None = None
    user_author_id: UUID | None = None
    flow_author_id: UUID | None = None
    user_assignee_id: UUID | None = None
    flow_assignee_id: UUID | None = None
    category: str | None = None
    status: str | None = None
    state: str | None = None
    result: dict[str, Any] | None = None

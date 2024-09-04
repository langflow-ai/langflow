from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Dict, Optional
from uuid import UUID, uuid4

from pydantic import field_serializer, field_validator
from sqlmodel import JSON, Column, Field, Relationship, SQLModel

if TYPE_CHECKING:
    from langflow.services.database.models.flow.model import Flow


class TaskBase(SQLModel):
    title: str
    description: str
    attachments: list[str] = Field(sa_column=Column(JSON))
    author_id: UUID = Field(foreign_key="flow.id", index=True)
    assignee_id: UUID = Field(foreign_key="flow.id", index=True)
    category: str
    state: str
    status: str = Field(default="pending")
    result: Optional[Dict] = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_serializer("created_at", "updated_at")
    def serialize_datetime(self, dt: datetime, _info):
        return dt.replace(microsecond=0).isoformat()

    @field_validator("created_at", "updated_at", mode="before")
    def validate_datetime(cls, v):
        if isinstance(v, datetime):
            return v
        return datetime.fromisoformat(v)

    @field_validator("status")
    def validate_status(cls, v):
        valid_statuses = ["pending", "processing", "completed", "failed"]
        if v not in valid_statuses:
            raise ValueError(f"Invalid status. Must be one of: {', '.join(valid_statuses)}")
        return v


class Task(TaskBase, table=True):  # type: ignore
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    author: Flow = Relationship(sa_relationship_kwargs={"primaryjoin": "Task.author_id==Flow.id"})
    assignee: Flow = Relationship(sa_relationship_kwargs={"primaryjoin": "Task.assignee_id==Flow.id"})


class TaskCreate(TaskBase):
    pass


class TaskRead(TaskBase):
    id: UUID


class TaskUpdate(SQLModel):
    status: Optional[str] = None
    state: Optional[str] = None
    result: Optional[Dict] = None

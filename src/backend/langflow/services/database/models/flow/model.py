# Path: src/backend/langflow/database/models/flow.py

from datetime import datetime
from typing import TYPE_CHECKING, Dict, Optional
from uuid import UUID, uuid4

from pydantic import field_serializer, field_validator
from sqlmodel import JSON, Column, Field, Relationship, SQLModel

if TYPE_CHECKING:
    from langflow.services.database.models.user import User


class FlowBase(SQLModel):
    name: str = Field(index=True)
    description: Optional[str] = Field(index=True, nullable=True, default=None)
    data: Optional[Dict] = Field(default=None, nullable=True)
    is_component: Optional[bool] = Field(default=False, nullable=True)
    updated_at: Optional[datetime] = Field(default_factory=datetime.utcnow, nullable=True)
    folder: Optional[str] = Field(default=None, nullable=True)

    @field_validator("data")
    def validate_json(v):
        if not v:
            return v
        if not isinstance(v, dict):
            raise ValueError("Flow must be a valid JSON")

        # data must contain nodes and edges
        if "nodes" not in v.keys():
            raise ValueError("Flow must have nodes")
        if "edges" not in v.keys():
            raise ValueError("Flow must have edges")

        return v

    # updated_at can be serialized to JSON
    @field_serializer("updated_at")
    def serialize_dt(self, dt: datetime, _info):
        if dt is None:
            return None
        return dt.isoformat()

    @field_validator("updated_at", mode="before")
    def validate_dt(cls, v):
        if v is None:
            return v
        elif isinstance(v, datetime):
            return v

        return datetime.fromisoformat(v)


class Flow(FlowBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True, unique=True)
    data: Optional[Dict] = Field(default=None, sa_column=Column(JSON))
    user_id: UUID = Field(index=True, foreign_key="user.id", nullable=True)
    user: "User" = Relationship(back_populates="flows")


class FlowCreate(FlowBase):
    user_id: Optional[UUID] = None


class FlowRead(FlowBase):
    id: UUID
    user_id: UUID = Field()


class FlowUpdate(SQLModel):
    name: Optional[str] = None
    description: Optional[str] = None
    data: Optional[Dict] = None

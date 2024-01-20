# Path: src/backend/langflow/database/models/flow.py

from langflow.services.database.models.base import SQLModelSerializable
from pydantic import validator

from sqlmodel import Field, JSON, Column, Relationship
from uuid import UUID, uuid4
from typing import Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from langflow.services.database.models.user import User


class FlowBase(SQLModelSerializable):
    name: str = Field(index=True)
    description: Optional[str] = Field(index=True)
    data: Optional[Dict] = Field(default=None, nullable=True)

    @validator("data")
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


class Flow(FlowBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True, unique=True)
    data: Optional[Dict] = Field(default=None, sa_column=Column(JSON))
    user_id: UUID = Field(index=True, foreign_key="user.id")
    user: "User" = Relationship(back_populates="flows")


class FlowCreate(FlowBase):
    user_id: Optional[UUID] = None


class FlowRead(FlowBase):
    id: UUID
    user_id: UUID = Field()


class FlowUpdate(SQLModelSerializable):
    name: Optional[str] = None
    description: Optional[str] = None
    data: Optional[Dict] = None

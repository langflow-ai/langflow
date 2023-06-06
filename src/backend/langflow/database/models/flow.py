# Path: src/backend/langflow/database/models/flow.py

from langflow.database.models.base import SQLModelSerializable
from pydantic import validator
from sqlmodel import Field, Relationship, JSON, Column
from uuid import UUID, uuid4
from typing import Dict, Optional

# if TYPE_CHECKING:
from langflow.database.models.flow_style import FlowStyle, FlowStyleRead


class FlowBase(SQLModelSerializable):
    name: str = Field(index=True)
    flow: Optional[Dict] = Field(default_factory=dict, sa_column=Column(JSON))

    @validator("flow")
    def validate_json(v):
        # dict_keys(['description', 'name', 'id', 'data'])
        if not v:
            return v
        if not isinstance(v, dict):
            raise ValueError("Flow must be a valid JSON")
        if "description" not in v.keys():
            raise ValueError("Flow must have a description")
        if "data" not in v.keys():
            raise ValueError("Flow must have data")

        # data must contain nodes and edges
        if "nodes" not in v["data"].keys():
            raise ValueError("Flow must have nodes")
        if "edges" not in v["data"].keys():
            raise ValueError("Flow must have edges")

        return v


class Flow(FlowBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True, unique=True)
    style: Optional["FlowStyle"] = Relationship(
        back_populates="flow", sa_relationship_kwargs={"uselist": False}
    )


class FlowCreate(FlowBase):
    pass


class FlowRead(FlowBase):
    id: UUID


class FlowReadWithStyle(FlowRead):
    style: Optional["FlowStyleRead"] = None


class FlowUpdate(SQLModelSerializable):
    name: Optional[str] = None
    flow: Optional[Dict] = None

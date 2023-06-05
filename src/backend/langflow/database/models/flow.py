from pydantic import validator
from sqlmodel import Field, SQLModel, Relationship, JSON, Column
from uuid import UUID, uuid4
from typing import TYPE_CHECKING, Dict

if TYPE_CHECKING:
    from langflow.database.models.flowstyle import FlowStyle


class FlowBase(SQLModel):
    name: str = Field(index=True)
    flow: Dict = Field(default_factory=dict, sa_column=Column(JSON))
    style: "FlowStyle" = Relationship(back_populates="flow")

    @validator("flow")
    def validate_json(v):
        # dict_keys(['description', 'name', 'id', 'data'])
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

    # @validator("flow")
    # def flow_must_be_json(cls, v):
    #     try:
    #         valid_json = json.loads(v)

    #     except Exception as e:
    #         raise ValueError(f"Flow must be a valid JSON: {e}") from e
    #     return v


class Flow(FlowBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True, unique=True)


class FlowCreate(FlowBase):
    pass


class FlowRead(FlowBase):
    id: UUID

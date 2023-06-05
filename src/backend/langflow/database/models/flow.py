from sqlmodel import Field, SQLModel, Relationship
from uuid import UUID, uuid4
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langflow.database.models.flowstyle import FlowStyle


class FlowBase(SQLModel):
    name: str = Field(index=True)
    flow: str = Field(index=False)
    style: "FlowStyle" = Relationship(back_populates="flow")


class Flow(FlowBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True, unique=True)


class FlowCreate(FlowBase):
    pass


class FlowRead(FlowBase):
    id: UUID

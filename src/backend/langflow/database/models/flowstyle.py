from sqlmodel import Field, SQLModel, Relationship
from uuid import UUID, uuid4
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langflow.database.models.flow import Flow


class FlowStyleBase(SQLModel):
    color: str = Field(index=True)
    emoji: str = Field(index=False)
    flow_id: UUID = Field(default_factory=uuid4, foreign_key="flow.id")
    flow: "Flow" = Relationship(back_populates="style")


class FlowStyle(FlowStyleBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True, unique=True)


class FlowStyleCreate(FlowStyleBase):
    pass


class FlowStyleRead(FlowStyleBase):
    id: UUID

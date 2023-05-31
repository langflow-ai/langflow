from sqlmodel import Field, SQLModel
from uuid import UUID, uuid4


class FlowBase(SQLModel):
    name: str = Field(index=True)
    flow: str = Field(index=False)


class Flow(FlowBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True, unique=True)


class FlowCreate(FlowBase):
    pass


class FlowRead(FlowBase):
    id: UUID

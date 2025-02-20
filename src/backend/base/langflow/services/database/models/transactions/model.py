from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from pydantic import field_serializer, field_validator
from sqlmodel import JSON, Column, Field, Relationship, SQLModel

from langflow.serialization.constants import MAX_ITEMS_LENGTH, MAX_TEXT_LENGTH
from langflow.serialization.serialization import serialize

if TYPE_CHECKING:
    from langflow.services.database.models.flow.model import Flow


class TransactionBase(SQLModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    vertex_id: str = Field(nullable=False)
    target_id: str | None = Field(default=None)
    inputs: dict | None = Field(default=None, sa_column=Column(JSON))
    outputs: dict | None = Field(default=None, sa_column=Column(JSON))
    status: str = Field(nullable=False)
    error: str | None = Field(default=None)
    flow_id: UUID = Field(foreign_key="flow.id")

    # Needed for Column(JSON)
    class Config:
        arbitrary_types_allowed = True

    @field_validator("flow_id", mode="before")
    @classmethod
    def validate_flow_id(cls, value):
        if value is None:
            return value
        if isinstance(value, str):
            value = UUID(value)
        return value

    @field_serializer("inputs")
    def serialize_inputs(self, data) -> dict:
        return serialize(data, max_length=MAX_TEXT_LENGTH, max_items=MAX_ITEMS_LENGTH)

    @field_serializer("outputs")
    def serialize_outputs(self, data) -> dict:
        return serialize(data, max_length=MAX_TEXT_LENGTH, max_items=MAX_ITEMS_LENGTH)


class TransactionTable(TransactionBase, table=True):  # type: ignore[call-arg]
    __tablename__ = "transaction"
    id: UUID | None = Field(default_factory=uuid4, primary_key=True)
    flow: "Flow" = Relationship(back_populates="transactions")


class TransactionReadResponse(TransactionBase):
    id: UUID = Field(alias="transaction_id")
    flow_id: UUID

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from pydantic import field_validator
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from langflow.services.database.models.flow.model import Flow


class SubscriptionBase(SQLModel):
    flow_id: UUID = Field(foreign_key="flow.id", index=True)
    event_type: str
    category: str | None = None
    state: str | None = None

    @field_validator("event_type")
    def validate_event_type(cls, v):
        valid_event_types = ["task_created", "task_updated", "task_completed", "task_failed"]
        if v not in valid_event_types:
            msg = f"Invalid event_type. Must be one of: {', '.join(valid_event_types)}"
            raise ValueError(msg)
        return v


class Subscription(SubscriptionBase, table=True):  # type: ignore
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    flow: "Flow" = Relationship(back_populates="subscriptions")


class SubscriptionCreate(SubscriptionBase):
    pass


class SubscriptionRead(SubscriptionBase):
    id: UUID

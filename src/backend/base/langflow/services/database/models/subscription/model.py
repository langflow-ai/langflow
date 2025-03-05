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
    @classmethod
    def validate_event_type(cls, v):
        """Validate event type using a pattern-based approach.

        Valid patterns:
        - task_{action} - For task-related events (e.g., task_created)
        - {type}_{action} - For trigger-related events (e.g., gmail_message_received, schedule_triggered)
        """
        # Standard task events
        task_events = ["task_created", "task_updated", "task_completed", "task_failed"]

        if v in task_events:
            return v

        # For trigger events, validate the pattern: {type}_{action}
        parts = v.split("_")
        if len(parts) >= 2:  # noqa: PLR2004
            return v

        msg = (
            "Invalid event_type format. Must be either a standard task "
            f"event ({', '.join(task_events)}) or follow the pattern: type_action"
        )
        raise ValueError(msg)


class Subscription(SubscriptionBase, table=True):  # type: ignore[call-arg]
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    flow: "Flow" = Relationship(back_populates="subscriptions")


class SubscriptionCreate(SubscriptionBase):
    pass


class SubscriptionRead(SubscriptionBase):
    id: UUID

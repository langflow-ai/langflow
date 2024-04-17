from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from uuid import UUID, uuid4

from sqlmodel import Field, Relationship, SQLModel, Column, DateTime, func

if TYPE_CHECKING:
    from langflow.services.database.models.user.model import User
    from langflow.services.database.models.flow.model import Flow


class ObserverBase(SQLModel):
    # Include basic fields that might be updated
    event_key: Optional[str] = Field(None, description="The event key to which this observer is subscribed")
    component_id: Optional[str] = Field(
        None, description="Identifier for the component within the flow, no relational integrity enforced"
    )


class Observer(ObserverBase, table=True):
    id: Optional[UUID] = Field(
        default_factory=uuid4,
        primary_key=True,
        description="Unique ID for the observer",
    )
    # Relationships with User and Flow
    user_id: UUID = Field(foreign_key="user.id", description="User ID associated with this observer")
    flow_id: UUID = Field(foreign_key="flow.id", description="Flow ID associated with this observer")

    # Relationships
    user: "User" = Relationship(back_populates="observers")
    flow: "Flow" = Relationship(back_populates="observers")

    # Timestamps
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
        description="Creation time of the observer",
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), onupdate=func.now(), nullable=True),
        description="Last update time of the observer",
    )


class ObserverCreate(ObserverBase):
    # Used for creating an observer, might not include timestamps as those will be set by the database
    pass


class ObserverRead(SQLModel):
    id: UUID
    user_id: UUID
    flow_id: UUID
    event_key: Optional[str]
    component_id: Optional[str]


class ObserverUpdate(SQLModel):
    # Include fields that can be updated
    event_key: Optional[str] = Field(None, description="The event key to which this observer is subscribed")
    component_id: Optional[str] = Field(None, description="Identifier for the component within the flow")

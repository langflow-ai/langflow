from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from pydantic import field_validator
from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

if TYPE_CHECKING:
    from langflow.services.database.models.flow.model import Flow
    from langflow.services.database.models.task.model import Task
    from langflow.services.database.models.user.model import User


class EntityType(str, Enum):
    """Enum for entity types that can be associated with an Actor."""

    USER = "user"
    FLOW = "flow"


class ActorBase(SQLModel):
    """Base class for Actor, containing common fields.

    This defines the polymorphic association between Tasks and either Users or Flows.
    """

    # The entity type this actor represents (either 'user' or 'flow')
    entity_type: str = Field(index=True)

    # The ID of the referenced entity (either user.id or flow.id)
    entity_id: UUID = Field(index=True)

    @field_validator("entity_type")
    @classmethod
    def validate_entity_type(cls, v):
        valid_types = {e.value for e in EntityType}
        if v not in valid_types:
            msg = f"Invalid entity type: {v}"
            raise ValueError(msg)
        return v


class Actor(ActorBase, table=True):  # type: ignore[call-arg]
    """The Actor model serves as a polymorphic association between Tasks and either Users or Flows.

    This allows Tasks to reference either a User or a Flow as author or assignee.
    """

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    # Set table name and constraints
    __tablename__ = "actor"
    __table_args__ = (UniqueConstraint("entity_type", "entity_id", name="unique_entity_reference"),)

    # Task relationships - must match the back_populates names in Task model
    authored_tasks: list["Task"] = Relationship(
        back_populates="author", sa_relationship_kwargs={"primaryjoin": "Actor.id==Task.author_id"}
    )

    assigned_tasks: list["Task"] = Relationship(
        back_populates="assignee", sa_relationship_kwargs={"primaryjoin": "Actor.id==Task.assignee_id"}
    )

    @classmethod
    async def create_from_user(cls, session: AsyncSession, user_id: UUID) -> "Actor":
        """Create an Actor instance for a User."""
        # Check if an Actor already exists for this User
        query = select(cls).where((cls.entity_type == EntityType.USER) & (cls.entity_id == user_id))
        result = await session.exec(query)
        existing_actor = result.first()

        if existing_actor:
            return existing_actor

        # Create a new Actor for this User
        actor = cls(entity_type=EntityType.USER, entity_id=user_id)
        session.add(actor)
        await session.commit()
        await session.refresh(actor)
        return actor

    @classmethod
    async def create_from_flow(cls, session: AsyncSession, flow_id: UUID) -> "Actor":
        """Create an Actor instance for a Flow."""
        # Check if an Actor already exists for this Flow
        if isinstance(flow_id, str):
            flow_id = UUID(flow_id)
        query = select(cls).where((cls.entity_type == EntityType.FLOW) & (cls.entity_id == flow_id))
        result = await session.exec(query)
        existing_actor = result.first()

        if existing_actor:
            return existing_actor

        # Create a new Actor for this Flow
        actor = cls(entity_type=EntityType.FLOW, entity_id=flow_id)
        session.add(actor)
        await session.commit()
        await session.refresh(actor)
        return actor

    async def get_entity(self, session: AsyncSession) -> "User | Flow | None":
        """Get the actual User or Flow entity this Actor represents."""
        # Import here to avoid circular imports
        from langflow.services.database.models.flow.model import Flow
        from langflow.services.database.models.user.model import User

        if self.entity_type == EntityType.USER:
            query = select(User).where(User.id == self.entity_id)
            result = await session.exec(query)
            return result.first()
        if self.entity_type == EntityType.FLOW:
            query = select(Flow).where(Flow.id == self.entity_id)
            result = await session.exec(query)
            return result.first()

        return None

    async def get_name(self, session: AsyncSession) -> str | None:
        """Get the name of the entity this Actor represents."""
        entity = await self.get_entity(session)
        if entity:
            return getattr(entity, "name", None) or getattr(entity, "username", None)
        return None


class ActorCreate(ActorBase):
    """Schema for creating a new Actor."""


class ActorRead(ActorBase):
    """Schema for reading an Actor."""

    id: UUID
    name: str | None = None

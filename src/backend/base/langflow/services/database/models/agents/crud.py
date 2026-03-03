"""CRUD operations for Agent persistence."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlmodel import col, select

from langflow.services.database.models.agents.model import Agent

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.database.models.agents.schema import AgentCreate, AgentUpdate


async def create_agent(db: AsyncSession, user_id: UUID, data: AgentCreate) -> Agent:
    """Persist a new agent configuration."""
    agent = Agent(
        user_id=user_id,
        name=data.name,
        description=data.description,
        system_prompt=data.system_prompt,
        tool_components=data.tool_components,
        icon=data.icon,
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent


async def get_agent_by_id(db: AsyncSession, agent_id: UUID, user_id: UUID) -> Agent | None:
    """Fetch a single agent by ID, scoped to the owning user."""
    statement = select(Agent).where(Agent.id == agent_id, Agent.user_id == user_id)
    result = await db.exec(statement)
    return result.first()


async def get_agents_by_user(db: AsyncSession, user_id: UUID) -> list[Agent]:
    """Fetch all agents belonging to a user, newest first."""
    statement = select(Agent).where(Agent.user_id == user_id).order_by(col(Agent.created_at).desc())
    result = await db.exec(statement)
    return list(result.all())


async def update_agent(db: AsyncSession, agent_id: UUID, user_id: UUID, data: AgentUpdate) -> Agent | None:
    """Update an existing agent. Returns None if not found."""
    agent = await get_agent_by_id(db, agent_id, user_id)
    if agent is None:
        return None

    update_fields = data.model_dump(exclude_unset=True)
    for field_name, value in update_fields.items():
        setattr(agent, field_name, value)

    agent.updated_at = datetime.now(timezone.utc)
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent


async def delete_agent(db: AsyncSession, agent_id: UUID, user_id: UUID) -> bool:
    """Delete an agent. Returns True if deleted, False if not found."""
    agent = await get_agent_by_id(db, agent_id, user_id)
    if agent is None:
        return False

    await db.delete(agent)
    await db.commit()
    return True

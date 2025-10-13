from datetime import datetime, timezone
from typing import Optional, Sequence
from uuid import UUID

from fastapi import HTTPException, status
from sqlmodel import and_, col, delete, select, update
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.services.database.models.published_agent.model import PublishedAgent, PublishedAgentCreate, PublishedAgentUpdate


async def create_published_agent(
    session: AsyncSession, 
    published_agent: PublishedAgentCreate, 
    user_id: UUID
) -> PublishedAgent:
    """Create a new published agent by fetching flow data."""
    from langflow.services.database.models.flow.model import Flow
    
    # First, fetch the flow data
    flow_query = select(Flow).where(
        and_(
            Flow.id == published_agent.flow_id,
        )
    )
    flow_result = await session.exec(flow_query)
    flow = flow_result.first()
    
    if not flow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Flow not found or you don't have permission to publish it"
        )
    

    flow_data = flow.data.copy() if flow.data else {"nodes": [], "edges": []}
    

    display_name = published_agent.display_name if published_agent.display_name else flow.name
    description = published_agent.description if published_agent.description else flow.description
    

    agent_data = {
        "user_id": user_id,
        "flow_id": published_agent.flow_id,
        "data": flow_data,  
        "category_id": published_agent.category_id,
        "display_name": display_name, 
        "description": description,  
    }
    
    db_published_agent = PublishedAgent.model_validate(agent_data)
    session.add(db_published_agent)
    await session.commit()
    await session.refresh(db_published_agent)
    return db_published_agent


async def get_published_agent_by_id(
    session: AsyncSession, 
    published_agent_id: UUID, 
    user_id: UUID | None = None
) -> PublishedAgent | None:
    """Get a published agent by ID, optionally filtered by user."""
    query = select(PublishedAgent).where(
        and_(
            PublishedAgent.id == published_agent_id,
            PublishedAgent.deleted_at.is_(None)  # Only active agents
        )
    )
    if user_id:
        query = query.where(PublishedAgent.user_id == user_id)
    
    result = await session.exec(query)
    return result.first()


async def get_published_agents(
    session: AsyncSession,
    user_id: UUID | None = None,
    flow_id: UUID | None = None,
    category_id: str | None = None,
    is_published: bool | None = None,
    include_deleted: bool = False,
    skip: int = 0,
    limit: int = 100,
) -> Sequence[PublishedAgent]:
    """Get published agents with optional filtering."""
    query = select(PublishedAgent)
    
    # Base filter for deleted agents
    if not include_deleted:
        query = query.where(PublishedAgent.deleted_at.is_(None))
    
    if user_id:
        query = query.where(PublishedAgent.user_id == user_id)
    if flow_id:
        query = query.where(PublishedAgent.flow_id == flow_id)
    if category_id:
        query = query.where(PublishedAgent.category_id == category_id)
    if is_published is not None:
        query = query.where(PublishedAgent.is_published == is_published)
    
    query = query.offset(skip).limit(limit).order_by(col(PublishedAgent.created_at).desc())
    
    result = await session.exec(query)
    return result.all()


async def get_published_agents_count(
    session: AsyncSession,
    user_id: UUID | None = None,
    flow_id: UUID | None = None,
    category_id: str | None = None,
    is_published: bool | None = None,
    include_deleted: bool = False,
) -> int:
    """Get count of published agents with optional filtering."""
    from sqlalchemy import func
    
    query = select(func.count(PublishedAgent.id))
    
    # Base filter for deleted agents
    if not include_deleted:
        query = query.where(PublishedAgent.deleted_at.is_(None))
    
    if user_id:
        query = query.where(PublishedAgent.user_id == user_id)
    if flow_id:
        query = query.where(PublishedAgent.flow_id == flow_id)
    if category_id:
        query = query.where(PublishedAgent.category_id == category_id)
    if is_published is not None:
        query = query.where(PublishedAgent.is_published == is_published)
    
    result = await session.exec(query)
    return result.first() or 0


async def update_published_agent(
    session: AsyncSession,
    published_agent_id: UUID,
    published_agent_update: PublishedAgentUpdate,
    user_id: UUID | None = None,
) -> PublishedAgent | None:
    """Update a published agent."""
    query = select(PublishedAgent).where(
        and_(
            PublishedAgent.id == published_agent_id,
            PublishedAgent.deleted_at.is_(None)  # Only update non-deleted agents
        )
    )
    if user_id:
        query = query.where(PublishedAgent.user_id == user_id)
    
    result = await session.exec(query)
    db_published_agent = result.first()
    
    if not db_published_agent:
        return None
    
    # Update fields
    update_data = published_agent_update.model_dump(exclude_unset=True)
    if update_data:
        for field, value in update_data.items():
            setattr(db_published_agent, field, value)
        
        session.add(db_published_agent)
        await session.commit()
        await session.refresh(db_published_agent)
    
    return db_published_agent


async def delete_published_agent(
    session: AsyncSession,
    published_agent_id: UUID,
    user_id: UUID | None = None,
    hard_delete: bool = False,
) -> bool:
    """Delete a published agent (soft delete by default)."""
    if not hard_delete:
        # Soft delete - mark as deleted
        query = select(PublishedAgent).where(PublishedAgent.id == published_agent_id)
        if user_id:
            query = query.where(PublishedAgent.user_id == user_id)
        
        result = await session.exec(query)
        db_published_agent = result.first()
        
        if not db_published_agent:
            return False
        
        # Use the soft_delete method from the model
        db_published_agent.soft_delete()
        session.add(db_published_agent)
        await session.commit()
        return True
    else:
        # Hard delete - remove from database
        delete_query = delete(PublishedAgent).where(PublishedAgent.id == published_agent_id)
        if user_id:
            delete_query = delete_query.where(PublishedAgent.user_id == user_id)
        
        result = await session.exec(delete_query)
        await session.commit()
        return result.rowcount > 0


async def restore_published_agent(
    session: AsyncSession,
    published_agent_id: UUID,
    user_id: UUID | None = None,
) -> bool:
    """Restore a soft-deleted published agent."""
    query = select(PublishedAgent).where(
        and_(
            PublishedAgent.id == published_agent_id,
            PublishedAgent.deleted_at.is_not(None)  # Only restore deleted agents
        )
    )
    if user_id:
        query = query.where(PublishedAgent.user_id == user_id)
    
    result = await session.exec(query)
    db_published_agent = result.first()
    
    if not db_published_agent:
        return False
    
    # Restore the agent
    db_published_agent.deleted_at = None
    db_published_agent.is_published = True
    
    session.add(db_published_agent)
    await session.commit()
    return True


async def toggle_published_agent_status(
    session: AsyncSession,
    published_agent_id: UUID,
    user_id: UUID | None = None,
) -> PublishedAgent | None:
    """Toggle the published status of a published agent."""
    query = select(PublishedAgent).where(
        and_(
            PublishedAgent.id == published_agent_id,
            PublishedAgent.deleted_at.is_(None)  # Only toggle non-deleted agents
        )
    )
    if user_id:
        query = query.where(PublishedAgent.user_id == user_id)
    
    result = await session.exec(query)
    db_published_agent = result.first()
    
    if not db_published_agent:
        return None
    
    # Toggle the published status
    db_published_agent.is_published = not db_published_agent.is_published
    
    session.add(db_published_agent)
    await session.commit()
    await session.refresh(db_published_agent)
    
    return db_published_agent


async def get_published_agents_by_flow_id(
    session: AsyncSession,
    flow_id: UUID,
    user_id: UUID | None = None,
    is_published: bool | None = None,
    include_deleted: bool = False,
) -> Sequence[PublishedAgent]:
    """Get all published agents for a specific flow."""
    query = select(PublishedAgent).where(PublishedAgent.flow_id == flow_id)
    
    # Base filter for deleted agents
    if not include_deleted:
        query = query.where(PublishedAgent.deleted_at.is_(None))
    
    if user_id:
        query = query.where(PublishedAgent.user_id == user_id)
    if is_published is not None:
        query = query.where(PublishedAgent.is_published == is_published)
    
    query = query.order_by(col(PublishedAgent.created_at).desc())
    
    result = await session.exec(query)
    return result.all()


async def get_published_agents_by_category(
    session: AsyncSession,
    category_id: str,
    user_id: UUID | None = None,
    is_published: bool | None = None,
    include_deleted: bool = False,
    skip: int = 0,
    limit: int = 100,
) -> Sequence[PublishedAgent]:
    """Get all published agents in a specific category."""
    query = select(PublishedAgent).where(PublishedAgent.category_id == category_id)
    
    # Base filter for deleted agents
    if not include_deleted:
        query = query.where(PublishedAgent.deleted_at.is_(None))
    
    if user_id:
        query = query.where(PublishedAgent.user_id == user_id)
    if is_published is not None:
        query = query.where(PublishedAgent.is_published == is_published)
    
    query = query.offset(skip).limit(limit).order_by(col(PublishedAgent.created_at).desc())
    
    result = await session.exec(query)
    return result.all()


async def get_published_agents_by_user(
    session: AsyncSession,
    user_id: UUID,
    is_published: bool | None = None,
    include_deleted: bool = False,
    skip: int = 0,
    limit: int = 100,
) -> Sequence[PublishedAgent]:
    """Get all published agents for a specific user."""
    query = select(PublishedAgent).where(PublishedAgent.user_id == user_id)
    
    # Base filter for deleted agents
    if not include_deleted:
        query = query.where(PublishedAgent.deleted_at.is_(None))
    
    if is_published is not None:
        query = query.where(PublishedAgent.is_published == is_published)
    
    query = query.offset(skip).limit(limit).order_by(col(PublishedAgent.created_at).desc())
    
    result = await session.exec(query)
    return result.all()


async def get_categories_with_count(
    session: AsyncSession,
    user_id: UUID | None = None,
    include_deleted: bool = False,
) -> dict[str, int]:
    """Get all categories with their published agent counts."""
    from sqlalchemy import func
    
    query = select(
        PublishedAgent.category_id,
        func.count(PublishedAgent.id).label('count')
    ).where(PublishedAgent.category_id.is_not(None))
    
    # Base filter for deleted agents
    if not include_deleted:
        query = query.where(PublishedAgent.deleted_at.is_(None))
    
    if user_id:
        query = query.where(PublishedAgent.user_id == user_id)
    
    query = query.group_by(PublishedAgent.category_id)
    
    result = await session.exec(query)
    return {category_id: count for category_id, count in result.all()}
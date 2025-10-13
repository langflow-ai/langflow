from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi_pagination import Page, Params
from fastapi_pagination.ext.sqlmodel import apaginate
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.services.database.models.published_agent.crud import (
    create_published_agent,
    delete_published_agent,
    get_published_agent_by_id,
    get_published_agents,
    get_published_agents_by_category,
    get_published_agents_by_flow_id,
    get_published_agents_count,
    restore_published_agent,
    toggle_published_agent_status,
    update_published_agent,
    get_categories_with_count,
)
from langflow.services.database.models.published_agent.model import (
    PublishedAgent,
    PublishedAgentCreate,
    PublishedAgentHeader,
    PublishedAgentRead,
    PublishedAgentUpdate,
)

router = APIRouter(prefix="/published-agents", tags=["Published Agents"])


class PublishedAgentResponse(BaseModel):
    """Response model for API operations."""
    message: str
    published_agent: PublishedAgentRead | None = None


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=PublishedAgentRead)
async def create_new_published_agent(
    published_agent: PublishedAgentCreate,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """Create a new published agent."""
    try:
        db_published_agent = await create_published_agent(session, published_agent, current_user.id)
        return db_published_agent
    except HTTPException:
        # Re-raise HTTP exceptions from the service layer
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create published agent: {str(e)}"
        ) from e


@router.get("/", response_model=Page[PublishedAgentHeader])
async def get_published_agents_list(
    session: DbSession,
    current_user: CurrentActiveUser,
    flow_id: Annotated[UUID | None, Query(description="Filter by flow ID")] = None,
    category_id: Annotated[str | None, Query(description="Filter by category ID")] = None,
    is_published: Annotated[bool | None, Query(description="Filter by published status")] = None,
    include_deleted: Annotated[bool, Query(description="Include deleted agents")] = False,
    params: Params = Depends(),
):
    """Get a paginated list of published agents."""
    published_agents = await get_published_agents(
        session=session,
        # user_id=current_user.id,
        flow_id=flow_id,
        category_id=category_id,
        is_published=is_published,
        include_deleted=include_deleted,
        skip=params.size * (params.page - 1),  # Fixed this line
        limit=params.size,
    )
    
    # Convert to paginated response
    total_count = await get_published_agents_count(
        session=session,
        # user_id=current_user.id,
        flow_id=flow_id,
        category_id=category_id,
        is_published=is_published,
        include_deleted=include_deleted,
    )
    
    # Create manual pagination since we're using service functions
    return Page.create(
        items=published_agents,  # Also add items= for clarity
        total=total_count,
        params=params,
    )


@router.get("/count", response_model=dict)
async def get_published_agents_count_endpoint(
    session: DbSession,
    current_user: CurrentActiveUser,
    flow_id: Annotated[UUID | None, Query(description="Filter by flow ID")] = None,
    category_id: Annotated[str | None, Query(description="Filter by category ID")] = None,
    is_published: Annotated[bool | None, Query(description="Filter by published status")] = None,
    include_deleted: Annotated[bool, Query(description="Include deleted agents")] = False,
):
    """Get the count of published agents with optional filters."""
    count = await get_published_agents_count(
        session=session,
        user_id=current_user.id,
        flow_id=flow_id,
        category_id=category_id,
        is_published=is_published,
        include_deleted=include_deleted,
    )
    return {"count": count}


@router.get("/{published_agent_id}", response_model=PublishedAgentRead)
async def get_published_agent_by_id_endpoint(
    published_agent_id: UUID,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """Get a specific published agent by ID."""
    db_published_agent = await get_published_agent_by_id(
        session, published_agent_id, current_user.id
    )
    if not db_published_agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Published agent not found"
        )
    return db_published_agent


@router.patch("/{published_agent_id}", response_model=PublishedAgentRead)
async def update_published_agent_endpoint(
    published_agent_id: UUID,
    published_agent_update: PublishedAgentUpdate,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """Update a published agent."""
    db_published_agent = await update_published_agent(
        session, published_agent_id, published_agent_update, current_user.id
    )
    if not db_published_agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Published agent not found"
        )
    return db_published_agent


@router.delete("/{published_agent_id}", response_model=PublishedAgentResponse)
async def delete_published_agent_endpoint(
    published_agent_id: UUID,
    session: DbSession,
    current_user: CurrentActiveUser,
    hard_delete: Annotated[bool, Query(description="Permanently delete instead of soft delete")] = False,
):
    """Delete a published agent."""
    success = await delete_published_agent(
        session, published_agent_id, current_user.id, hard_delete=hard_delete
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Published agent not found"
        )
    
    delete_type = "permanently deleted" if hard_delete else "deleted"
    return PublishedAgentResponse(
        message=f"Published agent {delete_type} successfully"
    )


@router.post("/{published_agent_id}/restore", response_model=PublishedAgentResponse)
async def restore_published_agent_endpoint(
    published_agent_id: UUID,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """Restore a soft-deleted published agent."""
    success = await restore_published_agent(session, published_agent_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Published agent not found or not deleted"
        )
    
    return PublishedAgentResponse(
        message="Published agent restored successfully"
    )


@router.post("/{published_agent_id}/toggle", response_model=PublishedAgentRead)
async def toggle_published_agent_status_endpoint(
    published_agent_id: UUID,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """Toggle the published status of a published agent."""
    db_published_agent = await toggle_published_agent_status(
        session, published_agent_id, current_user.id
    )
    if not db_published_agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Published agent not found"
        )
    return db_published_agent


@router.get("/by-flow/{flow_id}", response_model=list[PublishedAgentRead])
async def get_published_agents_by_flow(
    flow_id: UUID,
    session: DbSession,
    current_user: CurrentActiveUser,
    is_published: Annotated[bool | None, Query(description="Filter by published status")] = None,
    include_deleted: Annotated[bool, Query(description="Include deleted agents")] = False,
):
    """Get all published agents for a specific flow."""
    published_agents = await get_published_agents_by_flow_id(
        session=session,
        flow_id=flow_id,
        user_id=current_user.id,
        is_published=is_published,
        include_deleted=include_deleted,
    )
    return published_agents


@router.get("/by-category/{category_id}", response_model=Page[PublishedAgentHeader])
async def get_published_agents_by_category_endpoint(
    category_id: str,
    session: DbSession,
    current_user: CurrentActiveUser,
    is_published: Annotated[bool | None, Query(description="Filter by published status")] = None,
    include_deleted: Annotated[bool, Query(description="Include deleted agents")] = False,
    params: Params = Depends(),
):
    """Get all published agents in a specific category."""
    published_agents = await get_published_agents_by_category(
        session=session,
        category_id=category_id,
        user_id=current_user.id,
        is_published=is_published,
        include_deleted=include_deleted,
        skip=params.size * params.page,
        limit=params.size,
    )
    
    # Get total count for pagination
    total_count = await get_published_agents_count(
        session=session,
        user_id=current_user.id,
        category_id=category_id,
        is_published=is_published,
        include_deleted=include_deleted,
    )
    
    return Page.create(
        items=published_agents,
        total=total_count,
        params=params,
    )


@router.get("/published/list", response_model=Page[PublishedAgentHeader])
async def get_published_agents_only(
    session: DbSession,
    current_user: CurrentActiveUser,
    flow_id: Annotated[UUID | None, Query(description="Filter by flow ID")] = None,
    category_id: Annotated[str | None, Query(description="Filter by category ID")] = None,
    params: Params = Depends(),
):
    """Get only published (non-deleted, is_published=True) agents."""
    published_agents = await get_published_agents(
        session=session,
        user_id=current_user.id,
        flow_id=flow_id,
        category_id=category_id,
        is_published=True,
        include_deleted=False,
        skip=params.size * params.page,
        limit=params.size,
    )
    
    total_count = await get_published_agents_count(
        session=session,
        user_id=current_user.id,
        flow_id=flow_id,
        category_id=category_id,
        is_published=True,
        include_deleted=False,
    )
    
    return Page.create(
        items=published_agents,
        total=total_count,
        params=params,
    )


@router.get("/categories", response_model=dict[str, int])
async def get_categories_with_counts(
    session: DbSession,
    current_user: CurrentActiveUser,
    include_deleted: Annotated[bool, Query(description="Include deleted agents in counts")] = False,
):
    """Get all categories with their published agent counts."""
    categories = await get_categories_with_count(
        session=session,
        user_id=current_user.id,
        include_deleted=include_deleted,
    )
    return categories
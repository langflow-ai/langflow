"""API endpoints for background agent management."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.services.database.models.background_agent import (
    AgentStatus,
    BackgroundAgent,
    BackgroundAgentCreate,
    BackgroundAgentRead,
    BackgroundAgentUpdate,
)
from langflow.services.database.models.flow import Flow
from langflow.services.deps import get_background_agent_service

router = APIRouter(prefix="/background_agents", tags=["Background Agents"])


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=BackgroundAgentRead)
async def create_background_agent(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
    agent_data: BackgroundAgentCreate,
) -> BackgroundAgent:
    """Create a new background agent.

    Args:
        session: Database session
        current_user: Current authenticated user
        agent_data: Data for creating the agent

    Returns:
        Created background agent

    Raises:
        HTTPException: If flow not found or validation fails
    """
    # Verify flow exists and belongs to user
    flow = await session.get(Flow, agent_data.flow_id)
    if not flow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Flow {agent_data.flow_id} not found",
        )

    if flow.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to create agents for this flow",
        )

    # Create agent
    agent = BackgroundAgent(
        **agent_data.model_dump(),
        user_id=current_user.id,
        status=AgentStatus.STOPPED,
    )

    session.add(agent)
    await session.commit()
    await session.refresh(agent)

    return agent


@router.get("/", response_model=list[BackgroundAgentRead])
async def list_background_agents(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
    flow_id: UUID | None = None,
) -> list[BackgroundAgent]:
    """List background agents for the current user.

    Args:
        session: Database session
        current_user: Current authenticated user
        flow_id: Optional flow ID to filter by

    Returns:
        List of background agents
    """
    stmt = select(BackgroundAgent).where(BackgroundAgent.user_id == current_user.id)

    if flow_id:
        stmt = stmt.where(BackgroundAgent.flow_id == flow_id)

    result = await session.exec(stmt)
    return list(result.all())


@router.get("/{agent_id}", response_model=BackgroundAgentRead)
async def get_background_agent(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
    agent_id: UUID,
) -> BackgroundAgent:
    """Get a specific background agent.

    Args:
        session: Database session
        current_user: Current authenticated user
        agent_id: ID of the agent to retrieve

    Returns:
        Background agent

    Raises:
        HTTPException: If agent not found or access denied
    """
    agent = await session.get(BackgroundAgent, agent_id)

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent {agent_id} not found",
        )

    if agent.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to access this agent",
        )

    return agent


@router.patch("/{agent_id}", response_model=BackgroundAgentRead)
async def update_background_agent(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
    agent_id: UUID,
    agent_update: BackgroundAgentUpdate,
) -> BackgroundAgent:
    """Update a background agent.

    Args:
        session: Database session
        current_user: Current authenticated user
        agent_id: ID of the agent to update
        agent_update: Updated agent data

    Returns:
        Updated background agent

    Raises:
        HTTPException: If agent not found or access denied
    """
    agent = await session.get(BackgroundAgent, agent_id)

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent {agent_id} not found",
        )

    if agent.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to update this agent",
        )

    # Update fields
    update_data = agent_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(agent, key, value)

    session.add(agent)
    await session.commit()
    await session.refresh(agent)

    return agent


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_background_agent(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
    agent_id: UUID,
    background_agent_service: Annotated[object, Depends(get_background_agent_service)],
) -> None:
    """Delete a background agent.

    Args:
        session: Database session
        current_user: Current authenticated user
        agent_id: ID of the agent to delete
        background_agent_service: Background agent service

    Raises:
        HTTPException: If agent not found or access denied
    """
    agent = await session.get(BackgroundAgent, agent_id)

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent {agent_id} not found",
        )

    if agent.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to delete this agent",
        )

    # Stop agent if running
    if agent.status == AgentStatus.ACTIVE:
        try:
            await background_agent_service.stop_agent(agent_id)
        except Exception as e:  # noqa: BLE001
            # Log but continue with deletion even if stop fails
            from lfx.log.logger import logger
            
            await logger.awarning(f"Failed to stop agent {agent_id} during deletion: {e}")
            pass  # noqa: S110

    # Delete from database
    await session.delete(agent)
    await session.commit()


@router.post("/{agent_id}/start")
async def start_background_agent(
    *,
    current_user: CurrentActiveUser,
    session: DbSession,
    agent_id: UUID,
    background_agent_service: Annotated[object, Depends(get_background_agent_service)],
) -> dict:
    """Start a background agent.

    Args:
        current_user: Current authenticated user
        session: Database session
        agent_id: ID of the agent to start
        background_agent_service: Background agent service

    Returns:
        Status information

    Raises:
        HTTPException: If agent not found, access denied, or start fails
    """
    agent = await session.get(BackgroundAgent, agent_id)

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent {agent_id} not found",
        )

    if agent.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to start this agent",
        )

    try:
        result = await background_agent_service.start_agent(agent_id)
        return result
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start agent: {str(e)}",
        ) from e


@router.post("/{agent_id}/stop")
async def stop_background_agent(
    *,
    current_user: CurrentActiveUser,
    session: DbSession,
    agent_id: UUID,
    background_agent_service: Annotated[object, Depends(get_background_agent_service)],
) -> dict:
    """Stop a background agent.

    Args:
        current_user: Current authenticated user
        session: Database session
        agent_id: ID of the agent to stop
        background_agent_service: Background agent service

    Returns:
        Status information

    Raises:
        HTTPException: If agent not found, access denied, or stop fails
    """
    agent = await session.get(BackgroundAgent, agent_id)

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent {agent_id} not found",
        )

    if agent.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to stop this agent",
        )

    try:
        result = await background_agent_service.stop_agent(agent_id)
        return result
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop agent: {str(e)}",
        ) from e


@router.post("/{agent_id}/pause")
async def pause_background_agent(
    *,
    current_user: CurrentActiveUser,
    session: DbSession,
    agent_id: UUID,
    background_agent_service: Annotated[object, Depends(get_background_agent_service)],
) -> dict:
    """Pause a background agent.

    Args:
        current_user: Current authenticated user
        session: Database session
        agent_id: ID of the agent to pause
        background_agent_service: Background agent service

    Returns:
        Status information

    Raises:
        HTTPException: If agent not found, access denied, or pause fails
    """
    agent = await session.get(BackgroundAgent, agent_id)

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent {agent_id} not found",
        )

    if agent.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to pause this agent",
        )

    try:
        result = await background_agent_service.pause_agent(agent_id)
        return result
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to pause agent: {str(e)}",
        ) from e


@router.post("/{agent_id}/resume")
async def resume_background_agent(
    *,
    current_user: CurrentActiveUser,
    session: DbSession,
    agent_id: UUID,
    background_agent_service: Annotated[object, Depends(get_background_agent_service)],
) -> dict:
    """Resume a paused background agent.

    Args:
        current_user: Current authenticated user
        session: Database session
        agent_id: ID of the agent to resume
        background_agent_service: Background agent service

    Returns:
        Status information

    Raises:
        HTTPException: If agent not found, access denied, or resume fails
    """
    agent = await session.get(BackgroundAgent, agent_id)

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent {agent_id} not found",
        )

    if agent.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to resume this agent",
        )

    try:
        result = await background_agent_service.resume_agent(agent_id)
        return result
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to resume agent: {str(e)}",
        ) from e


@router.post("/{agent_id}/trigger")
async def trigger_background_agent(
    *,
    current_user: CurrentActiveUser,
    session: DbSession,
    agent_id: UUID,
    background_agent_service: Annotated[object, Depends(get_background_agent_service)],
) -> dict:
    """Manually trigger a background agent execution.

    Args:
        current_user: Current authenticated user
        session: Database session
        agent_id: ID of the agent to trigger
        background_agent_service: Background agent service

    Returns:
        Execution information

    Raises:
        HTTPException: If agent not found, access denied, or trigger fails
    """
    agent = await session.get(BackgroundAgent, agent_id)

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent {agent_id} not found",
        )

    if agent.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to trigger this agent",
        )

    try:
        result = await background_agent_service.trigger_agent(agent_id, trigger_source="manual")
        return result
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger agent: {str(e)}",
        ) from e


@router.get("/{agent_id}/status")
async def get_agent_status(
    *,
    current_user: CurrentActiveUser,
    session: DbSession,
    agent_id: UUID,
    background_agent_service: Annotated[object, Depends(get_background_agent_service)],
) -> dict:
    """Get the current status of a background agent.

    Args:
        current_user: Current authenticated user
        session: Database session
        agent_id: ID of the agent
        background_agent_service: Background agent service

    Returns:
        Agent status information

    Raises:
        HTTPException: If agent not found or access denied
    """
    agent = await session.get(BackgroundAgent, agent_id)

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent {agent_id} not found",
        )

    if agent.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to access this agent",
        )

    try:
        result = await background_agent_service.get_agent_status(agent_id)
        return result
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get agent status: {str(e)}",
        ) from e


@router.get("/{agent_id}/executions")
async def get_agent_executions(
    *,
    current_user: CurrentActiveUser,
    session: DbSession,
    agent_id: UUID,
    background_agent_service: Annotated[object, Depends(get_background_agent_service)],
    limit: int = 10,
    offset: int = 0,
) -> dict:
    """Get execution history for a background agent.

    Args:
        current_user: Current authenticated user
        session: Database session
        agent_id: ID of the agent
        background_agent_service: Background agent service
        limit: Maximum number of executions to return
        offset: Number of executions to skip

    Returns:
        List of execution records

    Raises:
        HTTPException: If agent not found or access denied
    """
    agent = await session.get(BackgroundAgent, agent_id)

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent {agent_id} not found",
        )

    if agent.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to access this agent",
        )

    try:
        executions = await background_agent_service.get_agent_executions(agent_id, limit=limit, offset=offset)
        return {"executions": executions, "count": len(executions)}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get agent executions: {str(e)}",
        ) from e

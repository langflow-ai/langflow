"""Security validation functions for flow ownership and access control."""

from uuid import UUID

from fastapi import HTTPException
from sqlmodel import AsyncSession, select

from langflow.services.database.models.flow.model import Flow


async def get_flow_with_ownership(
    session: AsyncSession,
    flow_id: UUID,
    user_id: UUID,
) -> Flow:
    """Get flow with MANDATORY ownership validation.

    This function ensures that a flow can only be accessed by its owner.
    It prevents cross-account access vulnerabilities by validating ownership
    at the database level.

    Args:
        session: Database session
        flow_id: UUID of the flow to retrieve
        user_id: UUID of the user requesting access

    Returns:
        Flow: The flow object if found and owned by user

    Raises:
        HTTPException: 404 if flow not found or not owned by user
    """
    stmt = select(Flow).where(Flow.id == flow_id, Flow.user_id == user_id)
    flow = (await session.exec(stmt)).first()
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")
    return flow


async def get_flow_with_ownership_by_name_or_id(
    session: AsyncSession,
    flow_id_or_name: str,
    user_id: UUID,
) -> Flow:
    """Get flow by ID or endpoint name with MANDATORY ownership validation.

    This function handles both UUID flow IDs and endpoint names while
    ensuring ownership validation.

    Args:
        session: Database session
        flow_id_or_name: Either UUID string or endpoint name
        user_id: UUID of the user requesting access

    Returns:
        Flow: The flow object if found and owned by user

    Raises:
        HTTPException: 404 if flow not found or not owned by user
    """
    try:
        # Try to parse as UUID first
        flow_uuid = UUID(flow_id_or_name)
        return await get_flow_with_ownership(session, flow_uuid, user_id)
    except ValueError as exc:
        # Not a UUID, treat as endpoint name
        stmt = select(Flow).where(Flow.endpoint_name == flow_id_or_name, Flow.user_id == user_id)
        flow = (await session.exec(stmt)).first()
        if not flow:
            raise HTTPException(status_code=404, detail="Flow not found") from exc
        return flow


async def get_public_flow_by_name_or_id(
    session: AsyncSession,
    flow_id_or_name: str,
) -> Flow:
    """Get public flow by ID or endpoint name without ownership validation.

    This function is ONLY for public flows that are explicitly marked as public.
    Use with extreme caution.

    Args:
        session: Database session
        flow_id_or_name: Either UUID string or endpoint name

    Returns:
        Flow: The public flow object if found

    Raises:
        HTTPException: 404 if flow not found or not public
    """
    from langflow.services.database.models.flow.model import AccessTypeEnum

    try:
        # Try to parse as UUID first
        flow_uuid = UUID(flow_id_or_name)
        stmt = select(Flow).where(Flow.id == flow_uuid, Flow.access_type == AccessTypeEnum.PUBLIC)
    except ValueError:
        # Not a UUID, treat as endpoint name
        stmt = select(Flow).where(Flow.endpoint_name == flow_id_or_name, Flow.access_type == AccessTypeEnum.PUBLIC)

    flow = (await session.exec(stmt)).first()
    if not flow:
        raise HTTPException(status_code=404, detail="Public flow not found")
    return flow

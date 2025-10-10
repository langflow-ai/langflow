from uuid import UUID

from fastapi import HTTPException
from sqlmodel import select

from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.user.model import User, UserRead
from langflow.services.deps import session_scope


async def get_user_by_flow_id_or_endpoint_name(
    flow_id_or_name: str, 
    requesting_user_id: UUID | None = None
) -> UserRead | None:
    """Get user by flow ID or endpoint name.
    
    Args:
        flow_id_or_name: Flow UUID string or endpoint name
        requesting_user_id: UUID of the user making the request (for ownership validation)
        
    Returns:
        UserRead: User information if flow is public or owned by requesting user
        
    Raises:
        HTTPException: If flow not found or access denied
    """
    from langflow.api.security import get_public_flow_by_name_or_id, get_flow_with_ownership_by_name_or_id
    
    async with session_scope() as session:
        flow = None
        
        # If requesting_user_id is provided, try to get flow with ownership validation first
        if requesting_user_id:
            try:
                flow = await get_flow_with_ownership_by_name_or_id(session, flow_id_or_name, requesting_user_id)
            except HTTPException:
                # If ownership fails, try public flow access
                pass
        
        # If no flow found with ownership, try public access
        if flow is None:
            flow = await get_public_flow_by_name_or_id(session, flow_id_or_name)

        user = await session.get(User, flow.user_id)
        if user is None:
            raise HTTPException(status_code=404, detail=f"User for flow {flow_id_or_name} not found")

        return UserRead.model_validate(user, from_attributes=True)

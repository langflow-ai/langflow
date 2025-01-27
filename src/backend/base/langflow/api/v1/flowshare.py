from fastapi import APIRouter, HTTPException
from langflow.api.utils import DbSession
from langflow.services.database.models.flows_share.model import FlowShare, FlowShareCreate, FlowShareRead
from langflow.services.database.models.flow import Flow  
from langflow.api.utils import CurrentActiveUser
from sqlmodel import select
from datetime import datetime, timezone
from langflow.services.database.models.user import User

router = APIRouter(prefix="/flows_share", tags=["Flows Share"])

@router.post("/", response_model=list[FlowShareRead], status_code=201)
async def create_flow_share(
    *,
    session: DbSession,
    flow_shares: list[FlowShareCreate],
    current_user: CurrentActiveUser,
):
    """Create a new flow share for a multiple recipients."""
    shared_flows = []
    existing_users_result = await session.exec(select(User.id))
    existing_users = set(existing_users_result.all())  

    for flow_share in flow_shares:
        if flow_share.shared_with not in existing_users:
            raise HTTPException(status_code=400, detail=f"User {flow_share.shared_with} does not exist in the database.")
        db_flow = await session.exec(select(Flow).where(Flow.id ==flow_share.flow_id).where(Flow.user_id == current_user.id))
        if not db_flow:
            raise HTTPException(status_code=403, detail="You do not have permission to share this flow.")
        db_flow_share = FlowShare(
            shared_with=flow_share.shared_with,  
            shared_by=current_user.id, 
            flow_id=flow_share.flow_id,
            created_at=datetime.now(timezone.utc), 
        )
        session.add(db_flow_share)
        shared_flows.append(db_flow_share)
    await session.commit()
    for db_flow_share in shared_flows:
        await session.refresh(db_flow_share)

    return shared_flows
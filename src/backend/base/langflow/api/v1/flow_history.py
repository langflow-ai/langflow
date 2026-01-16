from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from langflow.api.utils import DbSession
from langflow.helpers.flow_history import (
    FLOW_HISTORY_CHECKPOINT_NOT_FOUND_ERROR_MSG,
    FLOW_NOT_FOUND_ERROR_MSG,
    get_flow_checkpoint,
    list_flow_history,
    save_flow_checkpoint,
)
from langflow.services.auth.utils import get_current_active_user
from langflow.services.database.models.flow.model import Flow, FlowUpdate
from langflow.services.database.models.flow_history.model import FlowHistory
from langflow.services.database.models.user.model import User

router = APIRouter(prefix="/flows", tags=["Flow History"])


@router.get("/{flow_id}/history", response_model=dict, status_code=200)
async def get_flow_history(
    flow_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """List the history of the flow."""
    try:
        return await list_flow_history(
            user_id=current_user.id,
            flow_id=flow_id,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/{flow_id}/history/{version_id}", response_model=FlowHistory, status_code=200)
async def get_flow_history_checkpoint(
    current_user: Annotated[User, Depends(get_current_active_user)],
    version_id: UUID,
):
    """Get a specific version of the flow."""
    try:
        return await get_flow_checkpoint(
            user_id=current_user.id,
            version_id=version_id,
            )

    except Exception as e:
        if FLOW_HISTORY_CHECKPOINT_NOT_FOUND_ERROR_MSG in str(e):
            raise HTTPException(status_code=404, detail=str(e)) from e
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/{flow_id}/history", response_model=Flow, status_code=201)
async def create_flow_checkpoint(
    flow_id: UUID,
    flow: FlowUpdate,
    session: DbSession,
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Create a checkpoint for the flow."""
    try:
        # save_flow_checkpoint expects a dict for update_data
        updated_flow = await save_flow_checkpoint(
            session=session,
            user_id=current_user.id,
            flow_id=flow_id,
            update_data=flow.model_dump(exclude_unset=True),
        )
    except Exception as e:
        if FLOW_NOT_FOUND_ERROR_MSG in str(e):
            raise HTTPException(status_code=404, detail=str(e)) from e
        raise HTTPException(status_code=500, detail=str(e)) from e
    return updated_flow

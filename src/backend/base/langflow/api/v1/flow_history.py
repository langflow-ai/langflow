from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import NoResultFound

from langflow.api.utils import DbSession
from langflow.helpers.flow_history import (
    FLOW_HISTORY_CHECKPOINT_NOT_FOUND_ERROR_MSG,
    FLOW_NOT_FOUND_ERROR_MSG,
    delete_flow_checkpoint,
    get_flow_checkpoint,
    list_flow_history,
    save_flow_checkpoint,
)
from langflow.helpers.utils import MissingIdError
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
        flow_history = await list_flow_history(
            user_id=current_user.id,
            flow_id=flow_id,
            )
    except MissingIdError as e:
        raise HTTPException(status_code=400, detail="Missing user or flow.") from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return flow_history


@router.get("/{flow_id}/history/{version_id}", response_model=FlowHistory, status_code=200)
async def get_flow_history_checkpoint(
    current_user: Annotated[User, Depends(get_current_active_user)],
    version_id: UUID,
    ):
    """Get a specific version of the flow."""
    try:
        flow_checkpoint = await get_flow_checkpoint(
            user_id=current_user.id,
            version_id=version_id,
            )
    except MissingIdError as e:
        raise HTTPException(status_code=400, detail="Missing user or version.") from e
    except NoResultFound as e:
        raise HTTPException(status_code=404, detail=FLOW_HISTORY_CHECKPOINT_NOT_FOUND_ERROR_MSG) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return flow_checkpoint


@router.delete("/{flow_id}/history/{version_id}", response_model=dict, status_code=200)
async def delete_flow_history_checkpoint(
    current_user: Annotated[User, Depends(get_current_active_user)],
    version_id: UUID,
    ):
    """Delete a specific version of the flow."""
    try:
        version_id = await delete_flow_checkpoint(
            user_id=current_user.id,
            version_id=version_id,
            )
    except MissingIdError as e:
        raise HTTPException(status_code=400, detail="Missing user or version.") from e
    except NoResultFound as e:
        raise HTTPException(status_code=404, detail=FLOW_NOT_FOUND_ERROR_MSG) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return {"message": f"Flow history checkpoint {version_id} deleted successfully"}

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
    except MissingIdError as e:
        raise HTTPException(status_code=400, detail="Missing user or flow.") from e
    except NoResultFound as e:
        raise HTTPException(status_code=404, detail=FLOW_NOT_FOUND_ERROR_MSG) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return updated_flow

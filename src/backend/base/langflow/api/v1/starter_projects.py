from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from loguru import logger

from langflow.graph.graph.schema import GraphDump
from langflow.services.database.models.user.model import User
from langflow.services.auth.utils import get_current_active_user
from langflow.initial_setup.load import get_starter_projects_dump


router = APIRouter(prefix="/starter-projects", tags=["Flows"])


@router.get("/", response_model=List[GraphDump], status_code=200)
def get_starter_projects(
    *,
    current_user: User = Depends(get_current_active_user),
):
    """Get a list of starter projects."""
    try:
        flows = get_starter_projects_dump()
        return flows
    except Exception as exc:
        logger.error(exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

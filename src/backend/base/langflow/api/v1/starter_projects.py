from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from langflow.graph.graph.schema import GraphDump
from langflow.services.auth.utils import get_current_active_user
from langflow.services.database.models.user.model import User

router = APIRouter(prefix="/starter-projects", tags=["Flows"])


@router.get("/", response_model=list[GraphDump], status_code=200)
def get_starter_projects(
    *,
    current_user: User = Depends(get_current_active_user),
):
    """Get a list of starter projects."""
    from langflow.initial_setup.load import get_starter_projects_dump

    try:
        flows = get_starter_projects_dump()
        return flows
    except Exception as exc:
        logger.error(exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

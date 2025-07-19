from fastapi import APIRouter, Depends, HTTPException
from lfx.graph.graph.schema import GraphDump

from langflow.services.auth.utils import get_current_active_user

router = APIRouter(prefix="/starter-projects", tags=["Flows"])


@router.get("/", dependencies=[Depends(get_current_active_user)], status_code=200)
async def get_starter_projects() -> list[GraphDump]:
    """Get a list of starter projects."""
    from langflow.initial_setup.load import get_starter_projects_dump

    try:
        return get_starter_projects_dump()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

"""Discover the current Tool contract and revision of a reusable project."""

from uuid import UUID

from fastapi import APIRouter
from lfx.projects.tool_packs import ToolPackManifest

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.services.database.models.folder.tool_packs import resolve_tool_pack

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.get("/{project_id}/tool-pack", response_model=ToolPackManifest)
async def read_tool_pack(project_id: UUID, session: DbSession, current_user: CurrentActiveUser):
    manifest, _ = await resolve_tool_pack(session, current_user, project_id)
    return manifest

"""Reusable, authorized type guards for core and plugin project routes."""

from uuid import UUID

from fastapi import HTTPException
from lfx.projects import get_project_type
from sqlmodel import select

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.services.authorization import ProjectAction, ensure_project_permission
from langflow.services.authorization.fetch import authorized_or_owner_scoped, deny_to_404
from langflow.services.database.models.folder.model import Folder


def require_project_type(name: str, *, action=ProjectAction.READ, owner_only: bool = False):
    """Return a FastAPI dependency; authorize before reporting the actual project type."""

    async def guard(*, session: DbSession, current_user: CurrentActiveUser, project_id: UUID) -> Folder:
        if owner_only:
            project = (
                await session.exec(select(Folder).where(Folder.id == project_id, Folder.user_id == current_user.id))
            ).first()
        else:
            project = await authorized_or_owner_scoped(
                session,
                Folder,
                id_column=Folder.id,
                resource_id=project_id,
                owner_column=Folder.user_id,
                owner_id=current_user.id,
            )
        if project is None:
            raise HTTPException(404, "Project not found")
        try:
            await ensure_project_permission(
                current_user,
                action,
                project_id=project.id,
                project_user_id=project.user_id,
                workspace_id=project.workspace_id,
            )
        except HTTPException as exc:
            raise deny_to_404(exc, "Project not found") from exc
        try:
            definition = get_project_type(name)
        except ValueError as exc:
            raise HTTPException(422, "This project type is unavailable.") from exc
        if project.project_type != definition.name:
            raise HTTPException(422, f"Choose a project of type {definition.display_name}.")
        return project

    return guard

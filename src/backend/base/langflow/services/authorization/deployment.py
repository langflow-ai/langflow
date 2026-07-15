"""Authorization boundary for deployment flow-version references."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException, status
from sqlmodel import col, select

from langflow.initial_setup.setup import get_or_create_default_folder
from langflow.services.authorization.actions import DeploymentAction, FlowAction, ProjectAction
from langflow.services.authorization.fetch import deny_to_404
from langflow.services.authorization.guards import (
    ensure_deployment_permission,
    ensure_flow_permission,
    ensure_project_permission,
)
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.database.models.folder.model import Folder
from langflow.services.deps import get_authorization_service

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.database.models.user.model import User, UserRead


_FLOW_VERSION_NOT_FOUND = "Flow version not found."
_PROJECT_NOT_FOUND = "Project not found."


async def resolve_project_id_for_deployment_create(
    *,
    session: AsyncSession,
    current_user: User | UserRead,
    requested_project_id: UUID | None,
) -> UUID:
    """Resolve and authorize the project targeted by a deployment create.

    Explicit project lookup may cross owners only when the registered plugin
    opts in to cross-user fetch and enforcement is active. Both project access
    and deployment creation are checked with the real project owner/domain;
    missing and denied projects share the same non-disclosing response.
    """
    if requested_project_id is None:
        default_project = await get_or_create_default_folder(session, current_user.id)
        project_id = default_project.id
        project_user_id = current_user.id
        workspace_id = None
    else:
        authz = get_authorization_service()
        share_aware = await authz.supports_cross_user_fetch() and await authz.is_enabled()
        statement = select(Folder).where(Folder.id == requested_project_id)
        if not share_aware:
            statement = statement.where(Folder.user_id == current_user.id)
        project = (await session.exec(statement)).first()
        if project is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_PROJECT_NOT_FOUND)
        project_id = requested_project_id
        project_user_id = project.user_id
        workspace_id = project.workspace_id

    try:
        await ensure_project_permission(
            current_user,
            ProjectAction.READ,
            project_id=project_id,
            project_user_id=project_user_id,
            workspace_id=workspace_id,
        )
        await ensure_deployment_permission(
            current_user,
            DeploymentAction.CREATE,
            deployment_user_id=current_user.id,
            workspace_id=workspace_id,
            project_id=project_id,
        )
    except HTTPException as exc:
        raise deny_to_404(exc, detail=_PROJECT_NOT_FOUND) from exc
    return project_id


async def authorize_flow_versions_for_deployment(
    *,
    session: AsyncSession,
    current_user: User | UserRead,
    project_id: UUID,
    flow_version_ids: list[UUID],
) -> frozenset[UUID]:
    """Resolve and authorize every flow version referenced by a deployment mutation.

    Cross-user lookup is enabled only when a registered authorization service
    explicitly supports it and enforcement is active. Every resolved flow is
    then checked with ``flow:deploy``; a missing or denied reference returns the
    same 404 so callers cannot probe flow-version UUIDs.
    """
    unique_flow_version_ids = list(dict.fromkeys(flow_version_ids))
    if not unique_flow_version_ids:
        return frozenset()

    authz = get_authorization_service()
    share_aware = await authz.supports_cross_user_fetch() and await authz.is_enabled()

    statement = (
        select(
            col(FlowVersion.id).label("flow_version_id"),
            col(Flow.id).label("flow_id"),
            col(Flow.user_id).label("flow_user_id"),
            col(Flow.workspace_id).label("workspace_id"),
            col(Flow.folder_id).label("folder_id"),
        )
        .join(Flow, Flow.id == FlowVersion.flow_id)
        .where(
            col(FlowVersion.id).in_(unique_flow_version_ids),
            Flow.folder_id == project_id,
        )
    )
    if not share_aware:
        statement = statement.where(
            FlowVersion.user_id == current_user.id,
            Flow.user_id == current_user.id,
        )

    rows = list((await session.exec(statement)).all())
    rows_by_version_id = {row.flow_version_id: row for row in rows}
    if set(rows_by_version_id) != set(unique_flow_version_ids):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_FLOW_VERSION_NOT_FOUND)

    for flow_version_id in unique_flow_version_ids:
        row = rows_by_version_id[flow_version_id]
        try:
            await ensure_flow_permission(
                current_user,
                FlowAction.DEPLOY,
                flow_id=row.flow_id,
                flow_user_id=row.flow_user_id,
                workspace_id=row.workspace_id,
                folder_id=row.folder_id,
            )
        except HTTPException as exc:
            raise deny_to_404(exc, detail=_FLOW_VERSION_NOT_FOUND) from exc

    return frozenset(unique_flow_version_ids)


__all__ = ["authorize_flow_versions_for_deployment", "resolve_project_id_for_deployment_create"]

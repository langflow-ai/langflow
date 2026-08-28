"""Trusted request scope for model-provider policy decisions."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Query, status

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.services.authorization import (
    FlowAction,
    ProjectAction,
    authorized_or_owner_scoped,
    deny_to_404,
    ensure_flow_permission,
    ensure_project_permission,
)
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.folder.model import Folder
from langflow.services.model_provider_policy_scope import (
    ProviderPolicyAttributes,
    provider_policy_attributes_for_flow,
    scoped_model_provider_policy_for_flow,
)


async def resolve_provider_policy_attributes(
    current_user: CurrentActiveUser,
    session: DbSession,
    flow_id: Annotated[UUID | None, Query()] = None,
    project_id: Annotated[UUID | None, Query()] = None,
) -> ProviderPolicyAttributes:
    """Resolve an optional flow/project handle to its authorized server scope.

    Clients deliberately cannot supply a workspace id. The workspace is read
    from the selected project (or from a projectless stored flow).
    """
    if flow_id is not None and project_id is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Provide either flow_id or project_id, not both",
        )

    attributes: ProviderPolicyAttributes = {
        "is_superuser": bool(getattr(current_user, "is_superuser", False)),
    }
    if flow_id is not None:
        flow = await authorized_or_owner_scoped(
            session,
            Flow,
            id_column=Flow.id,
            resource_id=flow_id,
            owner_column=Flow.user_id,
            owner_id=current_user.id,
        )
        if flow is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found")
        try:
            await ensure_flow_permission(
                current_user,
                FlowAction.READ,
                flow_id=flow.id,
                flow_user_id=flow.user_id,
                workspace_id=flow.workspace_id,
                folder_id=flow.folder_id,
            )
        except HTTPException as exc:
            raise deny_to_404(exc, "Flow not found") from exc

        if flow.folder_id is not None:
            project = await session.get(Folder, flow.folder_id)
            if project is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
            attributes["project_id"] = project.id
            if project.workspace_id is not None:
                attributes["workspace_id"] = project.workspace_id
        elif flow.workspace_id is not None:
            attributes["workspace_id"] = flow.workspace_id
        return attributes

    if project_id is not None:
        project = await authorized_or_owner_scoped(
            session,
            Folder,
            id_column=Folder.id,
            resource_id=project_id,
            owner_column=Folder.user_id,
            owner_id=current_user.id,
        )
        if project is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        try:
            await ensure_project_permission(
                current_user,
                ProjectAction.READ,
                project_id=project_id,
                project_user_id=project.user_id,
                workspace_id=project.workspace_id,
            )
        except HTTPException as exc:
            raise deny_to_404(exc, "Project not found") from exc
        attributes["project_id"] = project.id
        if project.workspace_id is not None:
            attributes["workspace_id"] = project.workspace_id
    return attributes


ProviderPolicyAttributesDependency = Annotated[
    ProviderPolicyAttributes,
    Depends(resolve_provider_policy_attributes),
]


__all__ = [
    "ProviderPolicyAttributes",
    "ProviderPolicyAttributesDependency",
    "provider_policy_attributes_for_flow",
    "resolve_provider_policy_attributes",
    "scoped_model_provider_policy_for_flow",
]

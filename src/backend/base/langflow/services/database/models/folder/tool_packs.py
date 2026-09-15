"""Resolve a typed project's explicit tool exports within the caller's permissions."""

from uuid import UUID

from fastapi import HTTPException
from lfx.projects.tool_packs import ToolPackManifest, exported_flow_ids, tool_pack_manifest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.services.authorization import FlowAction, ProjectAction, ensure_flow_permission, ensure_project_permission
from langflow.services.authorization.fetch import authorized_or_owner_scoped, deny_to_404
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_authorization_service


def describe_tool_pack(project: Folder, flows: list[Flow]) -> ToolPackManifest:
    return tool_pack_manifest(
        project_id=project.id,
        name=project.name,
        config=project.project_config,
        flows=[
            {
                "id": str(flow.id),
                "name": flow.name,
                "description": flow.description,
                "data": flow.data,
                "is_component": flow.is_component,
            }
            for flow in flows
        ],
    )


async def resolve_tool_pack(
    session: AsyncSession, user: User, project_id: UUID, *, action: FlowAction = FlowAction.READ
) -> tuple[ToolPackManifest, list[Flow]]:
    project = await authorized_or_owner_scoped(
        session, Folder, id_column=Folder.id, resource_id=project_id, owner_column=Folder.user_id, owner_id=user.id
    )
    if project is None:
        raise HTTPException(404, "Tool pack not found")
    try:
        await ensure_project_permission(
            user,
            ProjectAction.READ,
            project_id=project.id,
            project_user_id=project.user_id,
            workspace_id=project.workspace_id,
        )
    except HTTPException as exc:
        raise deny_to_404(exc, "Tool pack not found") from exc
    if project.project_type != "tool-pack":
        raise HTTPException(422, "Choose a project of type Tool Pack.")
    try:
        ids = exported_flow_ids(project.project_config)
    except ValueError as exc:
        raise HTTPException(409, "The tool pack has invalid exports. Review its configuration.") from exc
    stmt = select(Flow).where(Flow.folder_id == project.id, Flow.id.in_(ids))
    authz = get_authorization_service()
    if not (await authz.supports_cross_user_fetch() and await authz.is_enabled()):
        stmt = stmt.where(Flow.user_id == user.id)
    flows = list((await session.exec(stmt)).all())
    for flow in flows:
        for permission in dict.fromkeys((FlowAction.READ, action)):
            try:
                await ensure_flow_permission(
                    user,
                    permission,
                    flow_id=flow.id,
                    flow_user_id=flow.user_id,
                    folder_id=project.id,
                    workspace_id=project.workspace_id,
                )
            except HTTPException as exc:
                raise deny_to_404(exc, "Tool pack not found") from exc
    try:
        manifest = describe_tool_pack(project, flows)
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(409, "The tool pack has invalid exports. Review its configuration.") from exc
    return manifest, flows

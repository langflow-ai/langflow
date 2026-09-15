"""Resolve a typed project's explicit tool exports within the caller's permissions."""

from copy import deepcopy
from uuid import UUID

from fastapi import HTTPException
from lfx.projects.bindings import flow_revision
from lfx.projects.tool_packs import ToolPackManifest, ToolPackToolBinding, exported_flow_ids, tool_pack_manifest
from lfx.schema.data import Data
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.services.authorization import FlowAction, ProjectAction, ensure_flow_permission, ensure_project_permission
from langflow.services.authorization.fetch import authorized_or_owner_scoped, deny_to_404
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_version.model import FlowVersion
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


async def resolve_tool_pack_snapshot(session: AsyncSession, user: User, binding: ToolPackToolBinding) -> Data:
    """Authorize current access, then load exactly the reviewed executable definition."""
    manifest, flows = await resolve_tool_pack(session, user, binding.reference.project_id, action=FlowAction.EXECUTE)
    if manifest.reference != binding.reference or binding.tool not in manifest.tools:
        msg = "The tool pack changed. Review its exports and save the harness before running it."
        raise ValueError(msg)
    source = next(flow for flow in flows if flow.id == binding.tool.flow_id)
    version = await session.get(FlowVersion, binding.version_id)
    if (
        version is None
        or version.flow_id != source.id
        or version.user_id != source.user_id
        or flow_revision(version.data) != binding.tool.revision
    ):
        msg = "The reviewed tool snapshot is unavailable. Review and save its Tool Pack reference again."
        raise ValueError(msg)
    return Data(
        data={
            "id": str(source.id),
            "name": binding.tool.name,
            "description": binding.tool.description,
            "data": deepcopy(version.data),
        }
    )

"""Resolve a typed project's explicit tool exports within the caller's permissions."""

from copy import deepcopy
from uuid import UUID

from fastapi import HTTPException
from lfx.projects.bindings import flow_revision
from lfx.projects.tool_packs import ToolPackManifest, ToolPackToolBinding, tool_pack_manifest
from lfx.schema.data import Data
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.services.authorization import FlowAction, ProjectAction, ensure_flow_permission, ensure_project_permission
from langflow.services.authorization.fetch import authorized_or_owner_scoped, deny_to_404
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.user.model import User

MAX_DEPENDENCY_FLOWS = 500


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


async def _read_pack(session: AsyncSession, user: User, project_id: UUID) -> Folder:
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
    return project


async def _authorize_flow(user: User, flow: Flow, action: FlowAction) -> None:
    for permission in dict.fromkeys((FlowAction.READ, action)):
        try:
            await ensure_flow_permission(
                user,
                permission,
                flow_id=flow.id,
                flow_user_id=flow.user_id,
                folder_id=flow.folder_id,
                workspace_id=flow.workspace_id,
            )
        except HTTPException as exc:
            raise deny_to_404(exc, "Tool pack dependency not found") from exc


async def resolve_tool_pack(
    session: AsyncSession,
    user: User,
    project_id: UUID,
    *,
    action: FlowAction = FlowAction.READ,
    _resolving: frozenset[UUID] = frozenset(),
) -> tuple[ToolPackManifest, list[Flow]]:
    from lfx.projects.lifecycle import ProjectConfigError
    from lfx.projects.source_resolution import resolve_tool_pack as resolve_sources

    from langflow.services.database.models.folder.save_context import LangflowProjectSaveContext, project_error_http

    try:
        manifest, sources = await resolve_sources(
            LangflowProjectSaveContext(session, user),
            project_id,
            access="execute" if action == FlowAction.EXECUTE else "read",
            resolving=_resolving,
        )
    except ProjectConfigError as exc:
        raise project_error_http(exc) from exc
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(
            409, "The tool pack has invalid exports or dependencies. Review its configuration."
        ) from exc
    return manifest, [await session.get(Flow, flow_id) for flow_id in sources]


async def resolve_tool_pack_snapshot(
    session: AsyncSession, user: User, binding: ToolPackToolBinding, *, require_current: bool = True
) -> Data:
    """Authorize current access, then load exactly the reviewed executable definition."""
    if require_current:
        manifest, _ = await resolve_tool_pack(session, user, binding.reference.project_id, action=FlowAction.EXECUTE)
        if manifest.reference != binding.reference or binding.tool not in manifest.tools:
            msg = "The tool pack changed. Review its exports and save the harness before running it."
            raise ValueError(msg)
    else:
        # Only a server-restored run may use its recorded revisions after an edit.
        # Current access/type checks still apply; no source code is taken from current rows.
        await _read_pack(session, user, binding.reference.project_id)
    recorded = binding.dependency_snapshots()
    definitions = {}
    for flow, version_id in [
        (binding.tool, binding.version_id),
        *[(item.flow, item.version_id) for item in recorded.values()],
    ]:
        source = await authorized_or_owner_scoped(
            session, Flow, id_column=Flow.id, resource_id=flow.flow_id, owner_column=Flow.user_id, owner_id=user.id
        )
        if source is None:
            raise HTTPException(404, "Tool pack dependency not found")
        await _authorize_flow(user, source, FlowAction.EXECUTE)
        version = await session.get(FlowVersion, version_id)
        if (
            version is None
            or version.flow_id != source.id
            or version.user_id != source.user_id
            or flow_revision(version.data or {}) != flow.revision
        ):
            msg = "The reviewed tool snapshot is unavailable. Review and save its Tool Pack reference again."
            raise ValueError(msg)
        definitions[str(flow.flow_id)] = {
            "id": str(flow.flow_id),
            "name": flow.name,
            "data": deepcopy(version.data),
            "description": getattr(flow, "description", None),
            "version_id": str(version_id),
        }
    return Data(data={**definitions[str(binding.tool.flow_id)], "dependencies": definitions})

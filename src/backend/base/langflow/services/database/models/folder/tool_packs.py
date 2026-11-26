"""Resolve a typed project's explicit tool exports within the caller's permissions."""

from copy import deepcopy
from uuid import UUID

from fastapi import HTTPException
from lfx.projects.bindings import flow_revision
from lfx.projects.dependencies import flow_references
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
    if project_id in _resolving:
        raise HTTPException(422, "The Tool Packs contain a recursive project reference.")
    resolving = _resolving | {project_id}
    project = await _read_pack(session, user, project_id)
    try:
        ids = exported_flow_ids(project.project_config)
    except ValueError as exc:
        raise HTTPException(409, "The tool pack has invalid exports. Review its configuration.") from exc
    stmt = select(Flow).where(Flow.folder_id == project.id, Flow.id.in_(ids))
    authz = get_authorization_service()
    if not (await authz.supports_cross_user_fetch() and await authz.is_enabled()):
        stmt = stmt.where(Flow.user_id == user.id)
    flows = list((await session.exec(stmt)).all())
    if {flow.id for flow in flows} != set(ids):
        raise HTTPException(409, "An exported tool is no longer available in its Tool Pack.")
    available = {str(flow.id): flow for flow in flows}
    pending = list(flows)
    while pending:
        source = pending.pop()
        await _authorize_flow(user, source, action)
        try:
            references = flow_references(source.data or {})
            bindings = [
                ToolPackToolBinding.model_validate(nested)
                for node in (source.data or {}).get("nodes", [])
                if (nested := (node.get("data", {}).get("_harness_tool") or {}).get("tool_pack"))
            ]
            # Persisted flow references use UUIDs; standalone resolution also supports
            # non-database IDs, so keep this check at the database boundary.
            for reference in references:
                if reference.flow_id:
                    UUID(reference.flow_id)
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            raise HTTPException(409, "The tool pack has invalid dependencies. Review its configuration.") from exc
        for binding in bindings:
            nested_manifest, _ = await resolve_tool_pack(
                session, user, binding.reference.project_id, action=action, _resolving=resolving
            )
            if binding.reference != nested_manifest.reference or binding.tool not in nested_manifest.tools:
                raise HTTPException(422, "A nested Tool Pack changed. Review its reference before using this export.")
        for reference in references:
            dependency = available.get(reference.flow_id)
            if dependency is not None:
                continue
            if reference.flow_id:
                dependency = await authorized_or_owner_scoped(
                    session,
                    Flow,
                    id_column=Flow.id,
                    resource_id=UUID(reference.flow_id),
                    owner_column=Flow.user_id,
                    owner_id=user.id,
                )
            else:
                # Legacy name references have always resolved inside the executing account.
                dependency = (
                    await session.exec(select(Flow).where(Flow.user_id == user.id, Flow.name == reference.name))
                ).first()
            if dependency is None:
                raise HTTPException(404, "Tool pack dependency not found")
            if str(dependency.id) not in available:
                available[str(dependency.id)] = dependency
                pending.append(dependency)
            if len(available) > MAX_DEPENDENCY_FLOWS:
                raise HTTPException(422, "A Tool Pack cannot depend on more than 500 flows.")
    flows = list(available.values())
    try:
        manifest = describe_tool_pack(project, flows)
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(409, "The tool pack has invalid exports. Review its configuration.") from exc
    return manifest, flows


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

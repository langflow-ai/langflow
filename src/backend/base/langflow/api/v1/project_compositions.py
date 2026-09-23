"""Export authorized project dependencies and import an isolated, atomic composition."""

from copy import deepcopy
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from fastapi import HTTPException
from lfx.projects.archives import (
    MAX_COMPOSITION_FLOWS,
    MAX_COMPOSITION_PROJECTS,
    ArchivedProject,
    CompositionGraph,
    ProjectComposition,
)
from lfx.projects.bindings import BINDING_ORIGIN, flow_revision
from lfx.projects.dependencies import flow_references
from lfx.projects.flow_slots import ProjectFlowBindings, flow_runtime_bindings
from lfx.projects.tool_packs import FlowDependencyVersion, ToolPackToolBinding, tool_pack_references
from lfx.projects.tools import TOOL_ORIGIN, tool_node_revision
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.api.utils import strip_flow_secrets
from langflow.api.v1.flows import create_flows
from langflow.api.v1.flows_helpers import _export_variable_names
from langflow.api.v1.schemas import FlowListCreate
from langflow.helpers.flow import generate_unique_flow_name
from langflow.helpers.folders import generate_unique_folder_name
from langflow.services.auth.mcp_encryption import encrypt_auth_settings
from langflow.services.authorization import (
    FlowAction,
    ProjectAction,
    ensure_project_permission,
    filter_visible_resources,
)
from langflow.services.authorization.fetch import authorized_or_owner_scoped, deny_to_404
from langflow.services.authorization.utils import _resolve_authz_domain
from langflow.services.creation_hooks import RESOURCE_PROJECT, PreCreationContext, enforce_pre_creation
from langflow.services.database.models.flow.model import Flow, FlowCreate, FlowRead
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.database.models.folder.model import Folder, FolderCreate
from langflow.services.database.models.folder.tool_packs import resolve_tool_pack
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_settings_service
from langflow.utils.flow_secrets import strip_structured_secret_values


async def export_composition(
    session: AsyncSession, user: User, root: Folder, root_flows: list[Flow]
) -> ProjectComposition:
    projects = {}
    rows = {}
    pending = [(root, root_flows)]
    while pending:
        project, flows = pending.pop()
        project_id = str(project.id)
        if project_id in projects:
            continue
        projects[project_id] = ArchivedProject(
            id=project.id,
            name=project.name,
            description=project.description,
            project_type=project.project_type,
            project_config=deepcopy(project.project_config),
            flows=[FlowRead.model_validate(flow, from_attributes=True).model_dump(mode="json") for flow in flows],
        )
        rows.update({str(flow.id): flow for flow in flows})
        references = list(tool_pack_references((project.project_config or {}).get("tool_packs", [])))
        for flow in flows:
            for node in (flow.data or {}).get("nodes", []):
                binding = node.get("data", {}).get(TOOL_ORIGIN, {}).get("tool_pack")
                if binding:
                    references.append(ToolPackToolBinding.model_validate(binding).reference)
        for reference in references:
            if str(reference.project_id) in projects:
                continue
            # The resolver owns project/export authorization, including shared-project policy.
            await resolve_tool_pack(session, user, reference.project_id)
            dependency = await session.get(Folder, reference.project_id)
            candidates = list(
                (
                    await session.exec(
                        select(Flow).where(Flow.folder_id == dependency.id, Flow.user_id == dependency.user_id)
                    )
                ).all()
            )
            visible = await filter_visible_resources(
                user,
                resource_type="flow",
                candidates=candidates,
                domain_extractor=lambda flow: _resolve_authz_domain(flow.workspace_id, flow.folder_id),
                owner_extractor=lambda flow: flow.user_id,
                act=FlowAction.READ,
            )
            pending.append((dependency, visible))
        # Ordinary nested flow calls may cross project boundaries too. Carry those
        # authorized projects instead of leaving IDs tied to the source installation.
        for flow in flows:
            for reference in flow_references(flow.data or {}):
                if reference.flow_id:
                    child = await authorized_or_owner_scoped(
                        session,
                        Flow,
                        id_column=Flow.id,
                        resource_id=UUID(reference.flow_id),
                        owner_column=Flow.user_id,
                        owner_id=user.id,
                    )
                else:
                    child = (
                        await session.exec(select(Flow).where(Flow.user_id == user.id, Flow.name == reference.name))
                    ).first()
                if child is None or child.folder_id is None:
                    raise HTTPException(404, "A referenced project flow is unavailable.")
                if str(child.folder_id) in projects:
                    continue
                dependency = await authorized_or_owner_scoped(
                    session,
                    Folder,
                    id_column=Folder.id,
                    resource_id=child.folder_id,
                    owner_column=Folder.user_id,
                    owner_id=user.id,
                )
                if dependency is None:
                    raise HTTPException(404, "A referenced project is unavailable.")
                try:
                    await ensure_project_permission(
                        user,
                        ProjectAction.READ,
                        project_id=dependency.id,
                        project_user_id=dependency.user_id,
                        workspace_id=dependency.workspace_id,
                    )
                except HTTPException as exc:
                    raise deny_to_404(exc, "A referenced project is unavailable.") from exc
                candidates = list(
                    (
                        await session.exec(
                            select(Flow).where(Flow.folder_id == dependency.id, Flow.user_id == dependency.user_id)
                        )
                    ).all()
                )
                visible = await filter_visible_resources(
                    user,
                    resource_type="flow",
                    candidates=candidates,
                    domain_extractor=lambda item: _resolve_authz_domain(item.workspace_id, item.folder_id),
                    owner_extractor=lambda item: item.user_id,
                    act=FlowAction.READ,
                )
                pending.append((dependency, visible))
        if len(projects) > MAX_COMPOSITION_PROJECTS or len(rows) > MAX_COMPOSITION_FLOWS:
            msg = "The composition exceeds the archive resource limit."
            raise ValueError(msg)
    composition = ProjectComposition(root_project_id=root.id, projects=list(projects.values()))
    graph = CompositionGraph(composition)
    graph.validate()
    # A stale or missing executable snapshot must not become a silently repaired handoff.
    versions = []
    for project in composition.projects:
        if project.project_type == "agent-harness":
            versions.extend(
                binding
                for _, binding in ProjectFlowBindings.model_validate(
                    (project.project_config or {}).get("flow_bindings", {})
                ).entries()
            )
        for flow in project.flows:
            versions.extend(binding for _, binding in flow_runtime_bindings(flow["data"]))
            for node in flow["data"].get("nodes", []):
                data = node.get("data", {})
                instruction = data.get(BINDING_ORIGIN)
                if instruction:
                    versions.extend(
                        binding
                        for _, binding in ProjectFlowBindings.model_validate(
                            {
                                "system_prompt": {
                                    key: value
                                    for key, value in instruction.items()
                                    if key not in {"project_id", "field_name"}
                                }
                            }
                        ).entries()
                    )
                pack = data.get(TOOL_ORIGIN, {}).get("tool_pack")
                if pack:
                    binding = ToolPackToolBinding.model_validate(pack)
                    versions.append(binding)
                    versions.extend(binding.dependency_versions)
    checked = set()
    for binding in versions:
        if not binding.version_id:
            continue
        if isinstance(binding, (ToolPackToolBinding, FlowDependencyVersion)):
            definition = binding.tool if isinstance(binding, ToolPackToolBinding) else binding.flow
            source_id, revision = str(definition.flow_id), definition.revision
        else:
            source_id, revision = binding.flow_id, binding.revision
        key = (str(binding.version_id), source_id, revision)
        if key in checked:
            continue
        checked.add(key)
        version = await session.get(FlowVersion, UUID(str(binding.version_id)))
        source = rows[source_id]
        if (
            version is None
            or version.flow_id != source.id
            or version.user_id != source.user_id
            or flow_revision(version.data or {}) != revision
        ):
            msg = "A reviewed source snapshot is unavailable. Review and save the harness before exporting."
            raise ValueError(msg)
    # Strip credentials before calculating the portable revisions. Archive version IDs are
    # deterministic placeholders; the importer always replaces them with server-owned IDs.
    variable_names_by_owner = {
        owner_id: await _export_variable_names(session, owner_id)
        for owner_id in {flow.user_id for flow in rows.values()}
    }
    sanitized = composition.model_copy(deep=True)
    for project in sanitized.projects:
        project.project_config = strip_structured_secret_values(project.project_config)
        for index, flow in enumerate(project.flows):
            clean = strip_flow_secrets(
                flow, known_variable_names=variable_names_by_owner[rows[str(flow["id"])].user_id]
            )
            for original_node, clean_node in zip(
                flow["data"].get("nodes", []), clean["data"].get("nodes", []), strict=True
            ):
                origin = clean_node.get("data", {}).get(TOOL_ORIGIN)
                if isinstance(origin, dict) and origin.get("applied_revision") == tool_node_revision(original_node):
                    origin["applied_revision"] = tool_node_revision(clean_node)
            project.flows[index] = clean
    return CompositionGraph(sanitized).relocate(
        project_ids={key: key for key in graph.projects},
        flow_ids={key: key for key in graph.flows},
        version_ids={key: str(uuid5(NAMESPACE_URL, f"langflow-archive:{key}")) for key in graph.flows},
    )


async def import_composition(session: AsyncSession, user: User, composition: ProjectComposition) -> list[FlowRead]:
    """Create every project/flow/version in the request transaction, returning root flows."""
    graph = CompositionGraph(composition)
    graph.validate(allow_missing_secrets=True)
    if not graph.projects[str(composition.root_project_id)].flows:
        msg = "The root project must contain at least one flow."
        raise ValueError(msg)
    project_ids = {key: str(uuid4()) for key in graph.projects}
    flow_ids = {key: str(uuid4()) for key in graph.flows}
    version_ids = {key: str(uuid4()) for key in graph.flows}
    names = {}
    used_names = set()
    for flow_id, flow in graph.flows.items():
        name = await generate_unique_flow_name(flow["name"], user.id, session)
        original_name = name
        suffix = 1
        while name in used_names:
            name = await generate_unique_flow_name(f"{original_name} ({suffix})", user.id, session)
            suffix += 1
        used_names.add(name)
        names[flow_id] = name
    relocated = graph.relocate(project_ids=project_ids, flow_ids=flow_ids, version_ids=version_ids, flow_names=names)
    folders = {}
    for project in relocated.projects:
        name = await generate_unique_folder_name(project.name, user.id, session)
        payload = FolderCreate(
            name=name,
            description=project.description,
            project_type=project.project_type,
            project_config=project.project_config,
        )
        await enforce_pre_creation(
            PreCreationContext(
                resource=RESOURCE_PROJECT,
                session=session,
                actor_user_id=user.id,
                requested_name=payload.name,
            )
        )
        folder = Folder.model_validate(payload, from_attributes=True)
        folder.id = project.id
        folder.user_id = user.id
        if not get_settings_service().auth_settings.AUTO_LOGIN:
            folder.auth_settings = encrypt_auth_settings({"auth_type": "apikey"})
        session.add(folder)
        await session.flush()
        folders[project.id] = folder
    flow_list = []
    for project in relocated.projects:
        for archived_flow in project.flows:
            # Import creates private project resources, not published endpoints or old scopes.
            data = {
                **archived_flow,
                "user_id": user.id,
                "folder_id": project.id,
                "workspace_id": folders[project.id].workspace_id,
                "endpoint_name": None,
            }
            flow_list.append(FlowCreate.model_validate(data))
    created = await create_flows(session=session, current_user=user, flow_list=FlowListCreate(flows=flow_list))
    created_by_id = {str(flow.id): flow for flow in created}
    for original_id, new_id in flow_ids.items():
        flow = created_by_id[new_id]
        session.add(
            FlowVersion(
                id=UUID(version_ids[original_id]),
                flow_id=flow.id,
                user_id=user.id,
                data=deepcopy(flow.data),
                version_number=1,
                description="Imported composition source",
            )
        )
    await session.flush()
    return [flow for flow in created if flow.folder_id == relocated.root_project_id]


def composition_error(exc: Exception) -> HTTPException:
    """Keep validation details useful without serializing Pydantic's entire input graph."""
    from pydantic import ValidationError

    message = "Invalid project composition." if isinstance(exc, ValidationError) else str(exc)
    return HTTPException(422, message)

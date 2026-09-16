"""Build an executable Harness candidate from authorized reviewed snapshots.

This is an explicit opt-in boundary. The legacy project artifact builder remains
unchanged: its consumers cannot preserve private definitions or candidate identity.
"""

import asyncio
import json
from copy import deepcopy
from functools import partial
from uuid import UUID

from lfx.projects.bindings import FlowBinding, flow_revision
from lfx.projects.dependencies import flow_references
from lfx.projects.flow_slots import flow_runtime_bindings
from lfx.projects.local_tools import LocalToolBinding
from lfx.projects.runtime_artifacts import MAX_EXPANDED_BYTES, MAX_FLOWS, build_candidate, candidate_nodes, canonical
from lfx.projects.tool_packs import ToolPackToolBinding
from sqlmodel import select

from langflow.services.authorization import FlowAction, ProjectAction, ensure_project_permission
from langflow.services.authorization.fetch import authorized_or_owner_scoped
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.folder.flow_bindings import _authorize, resolve_binding_snapshot
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.folder.tool_packs import resolve_tool_pack_snapshot
from langflow.services.deployment_artifacts.builder import (
    ProjectArtifactError,
    ProjectArtifactNotFoundError,
    _FlowSnapshot,
    _normalized_flow_bytes,
    _preflight_json_value,
    _run_sync_non_abandoning,
)

_PACKAGE_SLOTS = asyncio.Semaphore(2)


async def build_harness_artifact(session, user, project_id: UUID):
    """Return an authorized, sanitized candidate for an artifact-aware host."""
    async with _PACKAGE_SLOTS:
        return await _materialize_harness(session, user, project_id)


async def build_harness_download(session, user, project_id: UUID):
    """Keep archive construction off the event loop and inside the package budget."""
    async with _PACKAGE_SLOTS:
        candidate = await _materialize_harness(session, user, project_id)
        content = await _run_sync_non_abandoning(candidate.archive)
        return candidate, content


async def _materialize_harness(session, user, project_id: UUID):
    """Freeze the configured entrypoint and only its reachable definitions.

    Source read/deploy rights are required for every definition, including flows
    reached through shared packs. Snapshot resolution also checks execute rights.
    Names on legacy Run Flow references resolve only within the source owner.
    """
    project = await authorized_or_owner_scoped(
        session, Folder, id_column=Folder.id, resource_id=project_id, owner_column=Folder.user_id, owner_id=user.id
    )
    if project is None:
        msg = "Harness project not found"
        raise ProjectArtifactNotFoundError(msg)
    await ensure_project_permission(
        user,
        ProjectAction.READ,
        project_id=project.id,
        project_user_id=project.user_id,
        workspace_id=project.workspace_id,
    )
    root_id = (project.project_config or {}).get("agent_flow_id")
    if project.project_type != "agent-harness" or not root_id:
        msg = "Choose an Agent Harness with a saved entrypoint before packaging."
        raise ProjectArtifactError(msg)
    root = await _authorize(session, user, root_id, FlowAction.DEPLOY)
    if root.folder_id != project_id:
        msg = "The Harness entrypoint must belong to this project."
        raise ProjectArtifactError(msg)
    definitions = {}
    pending = []
    total_bytes = 0

    def include(item):
        nonlocal total_bytes
        identity = str(item["id"])
        existing = definitions.get(identity)
        if existing is not None:
            if canonical(existing) != canonical(item):
                msg = "Conflicting reviewed versions of the same dependency cannot be packaged."
                raise ProjectArtifactError(msg)
            return
        size, _ = _preflight_json_value(item, flow_id=UUID(identity), max_bytes=8 * 1024 * 1024, max_items=500_000)
        total_bytes += size
        if len(definitions) >= MAX_FLOWS or total_bytes > MAX_EXPANDED_BYTES:
            msg = "Harness candidate exceeds dependency or size limits."
            raise ProjectArtifactError(msg)
        definitions[identity] = deepcopy(item)
        pending.append(identity)

    include({"id": str(root.id), "name": root.name, "description": root.description or "", "data": root.data or {}})

    def live_revision(flow):
        return (flow_revision(flow.data or {}), flow.name, flow.description, flow.folder_id, flow.user_id)

    current_revisions = {str(root.id): live_revision(root)}
    while pending:
        identity = pending.pop()
        source = await _authorize(session, user, identity, FlowAction.DEPLOY)
        data = definitions[identity]["data"]
        flat_data = {"nodes": list(candidate_nodes(data))}
        bindings = list(flow_runtime_bindings(flat_data))
        for node in flat_data["nodes"]:
            inner = node.get("data", {})
            origin = inner.get("_harness_tool") or {}
            if pack := origin.get("tool_pack"):
                snapshot = await resolve_tool_pack_snapshot(
                    session, user, ToolPackToolBinding.model_validate(pack), require_current=False
                )
                for item in snapshot.data["dependencies"].values():
                    include({**item, "description": item.get("description") or ""})
            if local := origin.get("local_tool"):
                bindings.append(("tools", LocalToolBinding.model_validate(local)))
            instruction = inner.get("_harness_binding")
            if instruction and instruction.get("field_name") == "system_prompt":
                bindings.append(
                    (
                        "system_prompt",
                        FlowBinding.model_validate(
                            {
                                key: value
                                for key, value in instruction.items()
                                if key not in {"project_id", "field_name"}
                            }
                        ),
                    )
                )
        for field_name, binding in bindings:
            snapshot = await resolve_binding_snapshot(session, user, binding, field_name, require_current=False)
            for item in snapshot.data["dependencies"].values():
                include(item)
        for reference in flow_references(flat_data):
            target_id = reference.flow_id
            if target_id in definitions:
                continue
            if target_id is None:
                matches = list(
                    (
                        await session.exec(
                            select(Flow).where(Flow.user_id == source.user_id, Flow.name == reference.name)
                        )
                    ).all()
                )
                if len(matches) != 1:
                    msg = "A named Harness dependency is missing or ambiguous."
                    raise ProjectArtifactError(msg)
                target_id = str(matches[0].id)
                if target_id in definitions:
                    continue
            nested = await _authorize(session, user, target_id, FlowAction.DEPLOY)
            include(
                {
                    "id": target_id,
                    "name": nested.name,
                    "description": nested.description or "",
                    "data": nested.data or {},
                }
            )
            current_revisions[target_id] = live_revision(nested)

    # A candidate must never combine a root read before an edit with dependencies
    # read after that edit. Versioned rows are immutable; live rows are rechecked.
    for identity, revision in current_revisions.items():
        row = (
            await session.exec(
                select(Flow.data, Flow.name, Flow.description, Flow.folder_id, Flow.user_id).where(
                    Flow.id == UUID(identity)
                )
            )
        ).one_or_none()
        if row is None or (flow_revision(row[0] or {}), *row[1:]) != revision:
            msg = "Harness source changed during packaging. Retry from the saved configuration."
            raise ProjectArtifactError(msg)
    return await _run_sync_non_abandoning(partial(_pack_definitions, str(root.id), definitions))


def _pack_definitions(root_id, definitions):
    from lfx.utils.flow_requirements import generate_requirements_from_flow

    source_revisions = {identity: flow_revision(item["data"]) for identity, item in definitions.items()}
    sanitized = []
    variables = set()
    packages = set()

    for identity, item in definitions.items():
        content, required, _ = _normalized_flow_bytes(_FlowSnapshot(UUID(identity), item["name"], item))
        sanitized.append(json.loads(content))
        variables.update(required)
        packages.update(
            generate_requirements_from_flow({"data": {"nodes": list(candidate_nodes(item["data"]))}}, include_lfx=False)
        )
    return build_candidate(
        root_id,
        sanitized,
        source_revisions=source_revisions,
        required_variables=tuple(variables),
        packages=tuple(packages),
    )

"""Authorize and preserve the complete definition behind a harness customization."""

from copy import deepcopy
from uuid import UUID

from fastapi import HTTPException
from lfx.projects.bindings import flow_revision
from lfx.projects.dependencies import binding_dependencies, flow_references, validate_binding_dependencies
from lfx.projects.flow_slots import validate_project_binding
from lfx.projects.tool_packs import ToolPackToolBinding
from lfx.schema.data import Data
from sqlmodel import select

from langflow.services.authorization import FlowAction, ensure_flow_permission
from langflow.services.authorization.fetch import authorized_or_owner_scoped, deny_to_404
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.database.models.folder.tool_packs import MAX_DEPENDENCY_FLOWS, resolve_tool_pack


def flow_definitions(flows):
    return [
        {"id": str(flow.id), "name": flow.name, "description": flow.description or "", "data": flow.data or {}}
        for flow in flows
    ]


async def _authorize(session, user, flow_id, action):
    flow = await authorized_or_owner_scoped(
        session, Flow, id_column=Flow.id, resource_id=UUID(flow_id), owner_column=Flow.user_id, owner_id=user.id
    )
    if flow is None:
        raise HTTPException(404, "Harness flow dependency not found")
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
            raise deny_to_404(exc, "Harness flow dependency not found") from exc
    return flow


async def resolve_binding_flows(session, user, root, *, action=FlowAction.READ):
    """Walk static references within authorized current resources, without executing code."""
    available = {}
    pending = [str(root.id)]
    while pending:
        flow_id = pending.pop()
        if flow_id in available:
            continue
        source = await _authorize(session, user, flow_id, action)
        available[flow_id] = source
        if len(available) > MAX_DEPENDENCY_FLOWS:
            msg = "A harness customization cannot depend on more than 500 flows."
            raise ValueError(msg)
        for node in (source.data or {}).get("nodes", []):
            if value := (node.get("data", {}).get("_harness_tool") or {}).get("tool_pack"):
                binding = ToolPackToolBinding.model_validate(value)
                manifest, _ = await resolve_tool_pack(session, user, binding.reference.project_id, action=action)
                if manifest.reference != binding.reference or binding.tool not in manifest.tools:
                    msg = "A nested Tool Pack changed. Review its reference before binding this flow."
                    raise ValueError(msg)
        for reference in flow_references(source.data or {}):
            dependency_id = reference.flow_id
            if dependency_id is None:
                matches = list(
                    (await session.exec(select(Flow).where(Flow.user_id == user.id, Flow.name == reference.name))).all()
                )
                if len(matches) != 1:
                    msg = "A named harness flow dependency is missing or ambiguous."
                    raise ValueError(msg)
                dependency_id = str(matches[0].id)
            if dependency_id not in available:
                pending.append(dependency_id)
    # The shared traversal checks cycles and reviewed nested root revisions too.
    binding_dependencies(str(root.id), flow_definitions(available.values()))
    return available


async def resolve_binding_snapshot(session, user, binding, field_name, *, require_current=True):
    """Check current access and review, then read required versions rather than live code."""
    root = await _authorize(session, user, binding.flow_id, FlowAction.EXECUTE)
    if require_current or not binding.version_id:
        validate_project_binding(field_name, root.data or {}, binding)
        current = await resolve_binding_flows(session, user, root, action=FlowAction.EXECUTE)
        validate_binding_dependencies(binding, flow_definitions(current.values()))
    definitions = {}
    for item in [binding, *binding.dependencies]:
        source = root if item is binding else await _authorize(session, user, item.flow_id, FlowAction.EXECUTE)
        if not item.version_id:
            if binding.dependencies:
                msg = "The flow dependency snapshots are incomplete. Review and save the binding."
                raise ValueError(msg)
            data = source.data
        else:
            version = await session.get(FlowVersion, UUID(item.version_id))
            if (
                version is None
                or version.flow_id != source.id
                or version.user_id != source.user_id
                or flow_revision(version.data or {}) != item.revision
            ):
                msg = "A required flow dependency snapshot is unavailable. Review and save the binding."
                raise ValueError(msg)
            data = version.data
        definitions[item.flow_id] = {
            "id": item.flow_id,
            "name": source.name if item is binding else item.name,
            "description": (source.description or "") if item is binding else item.description,
            "data": deepcopy(data),
            "version_id": item.version_id,
        }
    validate_binding_dependencies(binding, list(definitions.values()))
    return Data(data={**definitions[binding.flow_id], "dependencies": definitions})

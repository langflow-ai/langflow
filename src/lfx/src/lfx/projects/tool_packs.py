"""Explicit Tool exports and content revisions for a reusable typed project."""

from __future__ import annotations

import hashlib
import json
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from lfx.projects.bindings import flow_revision
from lfx.projects.dependencies import dependency_ids


class ToolPackReference(BaseModel):
    """A reviewed project reference; resolving it must check its type and revision."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    project_id: UUID
    expected_type: Literal["tool-pack"] = "tool-pack"
    revision: str = Field(pattern=r"^[a-f0-9]{64}$")


class FlowDependency(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    flow_id: UUID
    name: str
    description: str = ""
    revision: str = Field(pattern=r"^[a-f0-9]{64}$")


class FlowDependencyVersion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    flow: FlowDependency
    version_id: UUID


class ToolExport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    flow_id: UUID
    name: str
    description: str = ""
    revision: str = Field(pattern=r"^[a-f0-9]{64}$")
    dependencies: tuple[FlowDependency, ...] = ()


class ToolPackManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    reference: ToolPackReference
    name: str
    tools: tuple[ToolExport, ...]


class ToolPackToolBinding(BaseModel):
    """The reviewed export and its server-created executable snapshot."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    reference: ToolPackReference
    tool: ToolExport
    version_id: UUID
    dependency_versions: tuple[FlowDependencyVersion, ...] = ()

    def dependency_snapshots(self) -> dict[str, FlowDependencyVersion]:
        """Require one executable snapshot for every reviewed nested definition."""
        expected = {str(item.flow_id): item for item in self.tool.dependencies}
        recorded = {str(item.flow.flow_id): item for item in self.dependency_versions}
        if (
            len(expected) != len(self.tool.dependencies)
            or len(recorded) != len(self.dependency_versions)
            or expected != {key: item.flow for key, item in recorded.items()}
        ):
            msg = "The reviewed tool dependency snapshots are incomplete. Review and save the Tool Pack reference."
            raise ValueError(msg)
        return recorded


class ToolDependencyUse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tool_call_id: str = Field(min_length=1)
    tool_name: str
    binding: ToolPackToolBinding


def tool_pack_references(value: object) -> tuple[ToolPackReference, ...]:
    if not isinstance(value, list):
        msg = "Tool packs must be a list of reviewed project references."
        raise TypeError(msg)
    references = tuple(ToolPackReference.model_validate(item) for item in value)
    if len({item.project_id for item in references}) != len(references):
        msg = "Select each tool pack only once."
        raise ValueError(msg)
    return references


def exported_flow_ids(config: dict | None) -> tuple[UUID, ...]:
    value = (config or {}).get("tools", [])
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        msg = "Exported tools must be a list of flow IDs from this project."
        raise ValueError(msg)
    return tuple(dict.fromkeys(UUID(item) for item in value))


def tool_pack_manifest(
    *, project_id: UUID, name: str, config: dict | None, flows: list[dict], dependency_flows: list[dict] | None = None
) -> ToolPackManifest:
    """Describe the selected exports from already-authorized, project-scoped flows.

    Revisions cover export membership, order, executable flow definitions, and tool
    names/descriptions. Pack labels, unexported flows, canvas positions, and MCP
    publication do not alter the tools a consumer reviewed. Reachable nested flow
    definitions are part of the reviewed export, including runtime flow bindings.
    """
    from lfx.projects.tools import validate_tool_flow

    available = {UUID(str(flow["id"])): flow for flow in flows if not flow.get("is_component", False)}
    definitions = {UUID(str(flow["id"])): flow for flow in [*(dependency_flows or []), *flows]}
    exports = []
    for flow_id in exported_flow_ids(config):
        if flow_id not in available:
            msg = "An exported tool is no longer available in this project."
            raise ValueError(msg)
        flow = available[flow_id]
        validate_tool_flow(flow)
        exports.append(
            ToolExport(
                flow_id=flow_id,
                name=flow["name"],
                description=flow.get("description") or "",
                revision=flow_revision(flow["data"]),
                dependencies=tuple(
                    FlowDependency(
                        flow_id=UUID(dependency_id),
                        name=definitions[UUID(dependency_id)]["name"],
                        description=definitions[UUID(dependency_id)].get("description") or "",
                        revision=flow_revision(definitions[UUID(dependency_id)]["data"]),
                    )
                    for dependency_id in dependency_ids(str(flow_id), list(definitions.values()))
                ),
            )
        )
    definition = {
        "project_id": str(project_id),
        "expected_type": "tool-pack",
        # Keep existing revisions stable for exports that have no nested dependencies.
        "tools": [
            export.model_dump(mode="json", exclude={"dependencies"} if not export.dependencies else set())
            for export in exports
        ],
    }
    revision = hashlib.sha256(json.dumps(definition, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return ToolPackManifest(
        reference=ToolPackReference(project_id=project_id, revision=revision), name=name, tools=tuple(exports)
    )

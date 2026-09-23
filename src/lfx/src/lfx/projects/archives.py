"""Closed project compositions: validate references, then relocate definitions children first.

This layer has no storage access. A missing reference is an error; an import must never
resolve an old ID or a coincidentally matching name against the receiving installation.
"""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from lfx.projects.bindings import BINDING_ORIGIN, flow_revision
from lfx.projects.flow_slots import (
    _RUNTIME_FIELDS,
    ProjectFlowBindings,
    flow_runtime_bindings,
    validate_project_binding,
)
from lfx.projects.tool_packs import ToolPackToolBinding, tool_pack_manifest, tool_pack_references
from lfx.projects.tools import TOOL_ORIGIN, tool_node_revision

MAX_COMPOSITION_PROJECTS = 100
MAX_COMPOSITION_FLOWS = 500


class ArchivedProject(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    name: str = Field(min_length=1)
    description: str | None = None
    project_type: Literal["flows", "agent-harness", "tool-pack"]
    project_config: dict | None = None
    flows: list[dict]


class ProjectComposition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format: Literal["langflow-composition"] = "langflow-composition"
    version: Literal[1] = 1
    root_project_id: UUID
    projects: list[ArchivedProject] = Field(min_length=1, max_length=MAX_COMPOSITION_PROJECTS)


class CompositionGraph:
    """Index only included resources and retain source identities while relocating them."""

    def __init__(self, composition: ProjectComposition):
        self.composition = composition
        self.projects = {str(project.id): project for project in composition.projects}
        self.flows: dict[str, dict] = {}
        self.owners: dict[str, str] = {}
        if len(self.projects) != len(composition.projects) or str(composition.root_project_id) not in self.projects:
            msg = "An archive needs unique project IDs and an included root project."
            raise ValueError(msg)
        for project in composition.projects:
            for flow in project.flows:
                flow_id = str(UUID(str(flow["id"])))
                if flow_id in self.flows:
                    msg = "An archive must contain unique flow IDs."
                    raise ValueError(msg)
                if not isinstance(flow.get("data"), dict) or not isinstance(flow.get("name"), str):
                    msg = "Every archived flow needs a name and a graph definition."
                    raise TypeError(msg)
                self.flows[flow_id] = flow
                self.owners[flow_id] = str(project.id)
        if len(self.flows) > MAX_COMPOSITION_FLOWS:
            msg = "A composition archive cannot contain more than 500 flows."
            raise ValueError(msg)

    def source(self, flow_id: str) -> dict:
        if flow_id not in self.flows:
            msg = "A referenced flow is missing from the composition archive."
            raise ValueError(msg)
        return self.flows[flow_id]

    def local_source(self, project_id: str, flow_id: str) -> dict:
        flow = self.source(flow_id)
        if self.owners[flow_id] != project_id:
            msg = "A project binding or local tool must belong to its archived project."
            raise ValueError(msg)
        return flow

    def manifest(self, project_id: str):
        project = self.projects.get(project_id)
        if project is None or project.project_type != "tool-pack":
            msg = "A referenced Tool Pack is missing from the composition archive."
            raise ValueError(msg)
        return tool_pack_manifest(
            project_id=project.id, name=project.name, config=project.project_config, flows=project.flows
        )

    def selected_flow(self, node: dict) -> str | None:
        data = node.get("data", {})
        if data.get("type") not in {"RunFlow", "SubFlow"}:
            return None
        template = data.get("node", {}).get("template", {})
        selected = template.get("flow_id_selected", {}).get("value")
        if selected:
            self.source(selected)
            return selected
        name = template.get("flow_name_selected", template.get("flow_name", {})).get("value")
        if not name:
            return None
        candidates = [flow_id for flow_id, flow in self.flows.items() if flow["name"] == name]
        if len(candidates) != 1:
            msg = "A named Run Flow dependency is missing or ambiguous in the archive."
            raise ValueError(msg)
        return candidates[0]

    def validate(self, *, allow_missing_secrets: bool = False) -> None:
        """Check reviewed definitions before any credential stripping or ID changes."""

        def validate_binding(field_name, data, binding):
            if not allow_missing_secrets:
                validate_project_binding(field_name, data, binding)
                return
            if flow_revision(data) != binding.revision:
                msg = "A bound flow changed from its archived revision."
                raise ValueError(msg)
            # Export intentionally removes credentials. Import validates the contract but
            # leaves its original required widgets intact for the recipient to configure.
            probe = deepcopy(data)
            for node in probe.get("nodes", []):
                for field in node.get("data", {}).get("node", {}).get("template", {}).values():
                    if isinstance(field, dict) and field.get("password") and field.get("value") in (None, "", []):
                        field["required"] = False
            validate_project_binding(field_name, probe, binding.model_copy(update={"revision": flow_revision(probe)}))

        for project_id, project in self.projects.items():
            config = project.project_config or {}
            if project.project_type == "tool-pack":
                self.manifest(project_id)
            if project.project_type != "agent-harness":
                continue
            if config.get("agent_flow_id"):
                self.local_source(project_id, config["agent_flow_id"])
            tools = config.get("tools", [])
            if not isinstance(tools, list) or any(not isinstance(item, str) for item in tools):
                msg = "Tools must be a list of flow IDs."
                raise ValueError(msg)
            for flow_id in tools:
                self.local_source(project_id, flow_id)
            for reference in tool_pack_references(config.get("tool_packs", [])):
                if reference != self.manifest(str(reference.project_id)).reference:
                    msg = "A Tool Pack changed. Review and save its reference before exporting."
                    raise ValueError(msg)
            for field_name, binding in ProjectFlowBindings.model_validate(config.get("flow_bindings", {})).entries():
                validate_binding(field_name, self.local_source(project_id, binding.flow_id)["data"], binding)
        for flow_id, flow in self.flows.items():
            for field_name, binding in flow_runtime_bindings(flow["data"]):
                validate_binding(field_name, self.source(binding.flow_id)["data"], binding)
            for node in flow["data"].get("nodes", []):
                target = self.selected_flow(node)
                data = node.get("data", {})
                for origin_name in (BINDING_ORIGIN, TOOL_ORIGIN):
                    origin = data.get(origin_name)
                    if not isinstance(origin, dict):
                        continue
                    if origin.get("project_id") != self.owners[flow_id] or origin.get("flow_id") != target:
                        msg = "An archived harness node has inconsistent project or flow references."
                        raise ValueError(msg)
                    if origin_name == BINDING_ORIGIN:
                        binding = ProjectFlowBindings.model_validate(
                            {
                                "system_prompt": {
                                    key: value
                                    for key, value in origin.items()
                                    if key not in {"project_id", "field_name"}
                                }
                            }
                        ).system_prompt
                        validate_binding("system_prompt", self.source(target)["data"], binding)
                    elif origin.get("tool_pack"):
                        binding = ToolPackToolBinding.model_validate(origin["tool_pack"])
                        manifest = self.manifest(str(binding.reference.project_id))
                        if binding.reference != manifest.reference or binding.tool not in manifest.tools:
                            msg = "An archived tool has an unreviewed Tool Pack definition."
                            raise ValueError(msg)
                        if str(binding.tool.flow_id) != target:
                            msg = "An archived tool targets a different flow from its reviewed export."
                            raise ValueError(msg)

    def relocate(
        self,
        *,
        project_ids: dict[str, str],
        flow_ids: dict[str, str],
        version_ids: dict[str, str],
        flow_names: dict[str, str] | None = None,
    ) -> ProjectComposition:
        """Rewrite known references, keeping canvas edits, baselines and all node/edge IDs.

        The caller validates the original composition first. Versions are allocated by
        the receiving server, never resolved from archive-supplied version IDs.
        """
        result = self.composition.model_copy(deep=True)
        target = CompositionGraph(result)
        visited: set[str] = set()
        active: set[str] = set()
        pack_manifests = {}
        names = flow_names or {flow_id: flow["name"] for flow_id, flow in self.flows.items()}

        def pack(project_id):
            if project_id not in pack_manifests:
                original = self.projects[project_id]
                for flow in original.flows:
                    visit(str(flow["id"]))
                project = target.projects[project_id]
                config = deepcopy(project.project_config or {})
                config["tools"] = [flow_ids[item] for item in config.get("tools", [])]
                pack_manifests[project_id] = tool_pack_manifest(
                    project_id=UUID(project_ids[project_id]), name=project.name, config=config, flows=project.flows
                )
            return pack_manifests[project_id]

        def binding_value(field_name, value):
            bindings = ProjectFlowBindings.model_validate({field_name: value}).entries()
            updated = []
            for _, binding in bindings:
                original_id = binding.flow_id
                visit(original_id)
                binding.flow_id = flow_ids[original_id]
                binding.revision = flow_revision(target.flows[original_id]["data"])
                binding.version_id = version_ids[original_id]
                updated.append(binding.model_dump())
            return updated if isinstance(value, list) else updated[0] if updated else None

        def visit(flow_id):
            if flow_id in active:
                msg = "The composition contains recursive flow or Tool Pack dependencies."
                raise ValueError(msg)
            if flow_id in visited:
                return
            self.source(flow_id)
            active.add(flow_id)
            flow = target.flows[flow_id]
            project_id = project_ids[self.owners[flow_id]]
            for node in flow["data"].get("nodes", []):
                data = node.get("data", {})
                template = data.get("node", {}).get("template", {})
                origin = data.get(TOOL_ORIGIN)
                unchanged_tool = isinstance(origin, dict) and origin.get("applied_revision") == tool_node_revision(node)
                selected = self.selected_flow(node)
                if selected:
                    visit(selected)
                    metadata = {"id": flow_ids[selected]}
                    if "flow_id_selected" in template:
                        template["flow_id_selected"]["value"] = flow_ids[selected]
                    if "flow_name_selected" in template:
                        template["flow_name_selected"].update(
                            value=names[selected],
                            options=[names[selected]],
                            options_metadata=[metadata],
                            selected_metadata=metadata,
                        )
                    elif "flow_name" in template:
                        template["flow_name"]["value"] = names[selected]
                if data.get("type") == "Agent":
                    for field_name, (input_name, origin_name, origin_key, _) in _RUNTIME_FIELDS.items():
                        raw = template.get(input_name, {}).get("value")
                        if raw and raw.strip() not in {"null", "{}", "[]"}:
                            template[input_name]["value"] = json.dumps(binding_value(field_name, json.loads(raw)))
                        runtime_origin = data.get(origin_name)
                        if isinstance(runtime_origin, dict):
                            runtime_origin["project_id"] = project_id
                            runtime_origin[origin_key] = binding_value(field_name, runtime_origin[origin_key])
                instruction = data.get(BINDING_ORIGIN)
                if isinstance(instruction, dict):
                    instruction.update(
                        project_id=project_id,
                        flow_id=flow_ids[selected],
                        revision=flow_revision(target.flows[selected]["data"]),
                        version_id=version_ids[selected],
                    )
                if isinstance(origin, dict):
                    origin.update(project_id=project_id, flow_id=flow_ids[selected])
                    if origin.get("tool_pack"):
                        original_binding = ToolPackToolBinding.model_validate(origin["tool_pack"])
                        manifest = pack(str(original_binding.reference.project_id))
                        export = next(item for item in manifest.tools if str(item.flow_id) == flow_ids[selected])
                        origin["tool_pack"] = ToolPackToolBinding(
                            reference=manifest.reference, tool=export, version_id=UUID(version_ids[selected])
                        ).model_dump(mode="json")
                    if unchanged_tool:
                        origin["applied_revision"] = tool_node_revision(node)
            flow.update(id=flow_ids[flow_id], name=names[flow_id])
            visited.add(flow_id)
            active.remove(flow_id)

        for flow_id in self.flows:
            visit(flow_id)
        for project_id, project in self.projects.items():
            if project.project_type == "tool-pack":
                pack(project_id)
        for project_id, project in target.projects.items():
            config = project.project_config
            if config is not None:
                if config.get("agent_flow_id"):
                    config["agent_flow_id"] = flow_ids[config["agent_flow_id"]]
                if "tools" in config:
                    config["tools"] = [flow_ids[item] for item in config["tools"]]
                if "tool_packs" in config:
                    config["tool_packs"] = [
                        pack(str(reference.project_id)).reference.model_dump(mode="json")
                        for reference in tool_pack_references(config["tool_packs"])
                    ]
                if "flow_bindings" in config:
                    config["flow_bindings"] = {
                        field_name: binding_value(field_name, value)
                        for field_name, value in config["flow_bindings"].items()
                    }
                if isinstance(config.get("_applied"), dict):
                    config["_applied"] = {
                        flow_ids[key]: value for key, value in config["_applied"].items() if key in flow_ids
                    }
            project.id = UUID(project_ids[project_id])
        result.root_project_id = UUID(project_ids[str(result.root_project_id)])
        return result

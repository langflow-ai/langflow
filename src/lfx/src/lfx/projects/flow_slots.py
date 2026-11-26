"""The executable project binding shapes, shared by saves, discovery, and archives."""

import json

from pydantic import BaseModel, ConfigDict, Field

from lfx.base.agents.hooks import HookBinding
from lfx.projects.bindings import FlowBinding, flow_revision
from lfx.projects.builtin_slots import BINDING_SLOTS, HARNESS_BINDING_SLOTS
from lfx.projects.compaction import CompactionBinding
from lfx.projects.context import ContextBinding
from lfx.projects.permissions import PermissionBinding
from lfx.projects.schema import Cardinality, ProjectTypeDefinition, SlotDefinition

BINDING_LABELS = {name: slot.binding_label for name, slot in HARNESS_BINDING_SLOTS.items()}


def runtime_binding_fields():
    return {
        name: (
            slot.agent_input_name,
            slot.origin_key,
            slot.origin_binding_key,
            [] if slot.cardinality == Cardinality.MULTI else None,
        )
        for name, slot in HARNESS_BINDING_SLOTS.items()
        if slot.origin_key
    }


class ProjectFlowBindings(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    system_prompt: FlowBinding | None = None
    hooks: list[HookBinding] = Field(default_factory=list)
    context_strategy: ContextBinding | None = None
    compaction: CompactionBinding | None = None
    tool_policy: PermissionBinding | None = None

    def entries(self) -> list[tuple[str, FlowBinding]]:
        return (
            ([("system_prompt", self.system_prompt)] if self.system_prompt else [])
            + [("hooks", binding) for binding in self.hooks]
            + ([("context_strategy", self.context_strategy)] if self.context_strategy else [])
            + ([("compaction", self.compaction)] if self.compaction else [])
            + ([("tool_policy", self.tool_policy)] if self.tool_policy else [])
        )


def binding_slot(field_name: str, project_type: ProjectTypeDefinition | None = None) -> SlotDefinition:
    if project_type is None:
        slot = BINDING_SLOTS.get(field_name)
    else:
        slot = next(
            (
                field.slot_definition
                for field in project_type.fields
                if field.name == field_name and field.supports_flow_binding
            ),
            None,
        )
    if slot is None:
        msg = "This field does not yet support flow bindings."
        raise ValueError(msg)
    return slot


def binding_outputs(field_name: str, data: dict, *, project_type: ProjectTypeDefinition | None = None) -> list[dict]:
    return binding_slot(field_name, project_type).binding_outputs(data)


def validate_project_binding(field_name: str, data: dict, binding: FlowBinding) -> None:
    binding_slot(field_name).validate_binding(data, binding)


def _runtime_values(node_data: dict) -> dict:
    template = node_data.get("node", {}).get("template", {})
    values = {}
    for field_name, (input_name, _, _, empty) in runtime_binding_fields().items():
        raw = template.get(input_name, {}).get("value")
        if raw is None or raw == "":
            raw = json.dumps(empty)
        if empty is None and isinstance(raw, str) and not raw.strip():
            raw = "null"
        value = json.loads(raw)
        values[field_name] = None if empty is None and value == {} else value
    return values


def flow_runtime_bindings(data: dict) -> list[tuple[str, FlowBinding]]:
    """Read embedded Agent references without importing saved component code."""
    return [
        entry
        for node in data.get("nodes", [])
        if node.get("data", {}).get("type") == "Agent"
        for entry in ProjectFlowBindings.model_validate(_runtime_values(node["data"])).entries()
    ]


def remap_runtime_bindings(
    flows: dict[str, dict], id_map: dict[str, str], project_id: str, *, flow_names: dict[str, str] | None = None
) -> None:
    """Remap all runtime contracts children first, after ordinary Run Flow links.

    A flow can contain Context, Compaction, Permission, and Hook references. One traversal ensures that each
    parent revision includes all child changes, independent of contract or archive order.
    Callers must validate original reviewed definitions before this mutates imported flows.
    """
    visited = set()
    original_ids = {new: old for old, new in id_map.items()}

    def visit(flow_id, active):
        if flow_id in active:
            msg = "The imported harness flows contain a recursive reference."
            raise ValueError(msg)
        if flow_id in visited:
            return
        data = flows[flow_id]

        def remap_dependencies(dependencies):
            from lfx.projects.bindings import BoundFlowDependency

            updated = []
            for item in dependencies:
                dependency = BoundFlowDependency.model_validate(item)
                target = dependency.flow_id
                visit(target, active | {flow_id})
                updated.append(
                    dependency.model_copy(
                        update={
                            "flow_id": id_map[target],
                            "name": (flow_names or {}).get(target, dependency.name),
                            "revision": flow_revision(flows[target]),
                            "version_id": None,
                        }
                    )
                )
            return updated

        def remap(field_name, value):
            bindings = ProjectFlowBindings.model_validate({field_name: value}).entries()
            updated = []
            for _, binding in bindings:
                target = binding.flow_id
                if target not in id_map:
                    msg = "An imported harness binding must reference a flow in the archive."
                    raise ValueError(msg)
                visit(target, active | {flow_id})
                updated.append(
                    binding.model_copy(
                        update={
                            "flow_id": id_map[target],
                            "revision": flow_revision(flows[target]),
                            "version_id": None,
                            **(
                                {"dependencies": remap_dependencies(binding.dependencies)}
                                if binding.dependencies
                                else {}
                            ),
                        }
                    ).model_dump()
                )
            return updated if isinstance(value, list) else updated[0] if updated else None

        for node in data.get("nodes", []):
            node_data = node.get("data", {})
            if node_data.get("type") in {"RunFlow", "SubFlow"}:
                template = node_data.get("node", {}).get("template", {})
                selected = template.get("flow_id_selected", {}).get("value")
                if selected in original_ids:
                    target = original_ids[selected]
                    visit(target, active | {flow_id})
                    tool_origin = node_data.get("_harness_tool") or {}
                    if tool_origin.get("local_tool"):
                        from lfx.projects.local_tools import LocalToolBinding

                        local = LocalToolBinding.model_validate(tool_origin["local_tool"])
                        local.flow_id = id_map[target]
                        local.name = (flow_names or {}).get(target, local.name)
                        local.revision = flow_revision(flows[target])
                        local.version_id = None
                        local.dependencies = remap_dependencies(local.dependencies)
                        tool_origin["local_tool"] = local.model_dump(mode="json")
                    instruction = node_data.get("_harness_binding")
                    if isinstance(instruction, dict):
                        instruction["revision"] = flow_revision(flows[target])
                        instruction["version_id"] = None
                        if instruction.get("dependencies"):
                            instruction["dependencies"] = [
                                item.model_dump() for item in remap_dependencies(instruction["dependencies"])
                            ]
            if node_data.get("type") != "Agent":
                continue
            values = _runtime_values(node_data)
            for field_name, (input_name, origin_name, origin_key, _) in runtime_binding_fields().items():
                if values[field_name]:
                    node_data["node"]["template"][input_name]["value"] = json.dumps(
                        remap(field_name, values[field_name])
                    )
                origin = node_data.get(origin_name)
                if isinstance(origin, dict):
                    origin["project_id"] = project_id
                    origin[origin_key] = remap(field_name, origin[origin_key])
        visited.add(flow_id)

    for flow_id in flows:
        visit(flow_id, set())

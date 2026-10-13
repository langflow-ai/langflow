"""Configuration archive contracts for the built-in project types."""

from copy import deepcopy
from uuid import UUID

from lfx.projects.archive_graphs import FlowArchiveGraph
from lfx.projects.bindings import flow_revision
from lfx.projects.dependencies import binding_dependencies, validate_binding_dependencies
from lfx.projects.flow_slots import ProjectFlowBindings, validate_project_binding
from lfx.projects.local_tools import local_tool_bindings, local_tool_definition, validate_local_tool_source
from lfx.projects.skills import skill_definitions, skill_pack_manifest, skill_pack_references
from lfx.projects.tool_packs import tool_pack_manifest, tool_pack_references


def _graph(ctx):
    from lfx.projects.archives import ArchivedProject, ProjectComposition

    return FlowArchiveGraph(
        ProjectComposition(
            root_project_id=UUID(ctx.project_id),
            projects=[ArchivedProject.model_validate(project) for project in ctx.projects.values()],
        )
    )


def validate_config(kind, config, ctx):
    graph = _graph(ctx)
    project_id = ctx.project_id
    config = config or {}

    def validate_binding(field_name, data, binding):
        validate_binding_dependencies(binding, list(ctx.flows.values()))
        if ctx.allow_missing_secrets:
            if flow_revision(data) != binding.revision:
                msg = "A bound flow changed from its archived revision."
                raise ValueError(msg)
            data = deepcopy(data)
            for node in data.get("nodes", []):
                for field in node.get("data", {}).get("node", {}).get("template", {}).values():
                    if isinstance(field, dict) and field.get("password") and field.get("value") in (None, "", []):
                        field["required"] = False
            binding = binding.model_copy(update={"revision": flow_revision(data)})
        validate_project_binding(field_name, data, binding)

    if kind == "tool-pack":
        graph.manifest(project_id)
    if kind == "skill-pack":
        graph.skill_manifest(project_id)
    if kind != "agent-harness":
        return
    if config.get("agent_flow_id"):
        graph.local_source(project_id, config["agent_flow_id"])
    tools = config.get("tools", [])
    if not isinstance(tools, list) or any(not isinstance(item, str) for item in tools):
        msg = "Tools must be a list of flow IDs."
        raise ValueError(msg)
    for flow_id in tools:
        graph.local_source(project_id, flow_id)
    for binding in local_tool_bindings(config.get("tool_bindings", {})).values():
        if binding.flow_id not in tools:
            msg = "An archived local tool binding is not selected by its harness."
            raise ValueError(msg)
        validate_local_tool_source(graph.local_source(project_id, binding.flow_id), binding)
        validate_binding_dependencies(binding, list(graph.flows.values()))
    for reference in tool_pack_references(config.get("tool_packs", [])):
        if reference != graph.manifest(str(reference.project_id)).reference:
            msg = "A Tool Pack changed. Review and save its reference before exporting."
            raise ValueError(msg)
    for reference in skill_pack_references(config.get("skill_packs", [])):
        if reference != graph.skill_manifest(str(reference.project_id)).reference:
            msg = "A Skill Pack changed. Review it before exporting."
            raise ValueError(msg)
    for field_name, binding in ProjectFlowBindings.model_validate(config.get("flow_bindings", {})).entries():
        validate_binding(field_name, graph.local_source(project_id, binding.flow_id)["data"], binding)


def harness_sources(config):
    config = config or {}
    return (
        *local_tool_bindings(config.get("tool_bindings", {})).values(),
        *(binding for _, binding in ProjectFlowBindings.model_validate(config.get("flow_bindings", {})).entries()),
    )


def skill_references(config):
    return tuple(ref for skill in skill_definitions((config or {}).get("skills", [])) for ref in skill.tool_packs)


def remap_config(kind, config, mapping):
    if config is None:
        return None
    config = deepcopy(config)
    sources = list(mapping.flows.values())
    originals = {new: old for old, new in mapping.flow_ids.items()}

    def dependencies(flow_id):
        result = binding_dependencies(flow_id, sources)
        for dependency in result:
            dependency.version_id = mapping.version_ids[originals[dependency.flow_id]]
        return result

    def pack(project_id):
        project = mapping.project(project_id, expected_type="tool-pack")
        value = deepcopy(project["project_config"] or {})
        value["tools"] = [mapping.flow_ids[item] for item in value.get("tools", [])]
        return tool_pack_manifest(
            project_id=UUID(mapping.project_ids[project_id]),
            name=project["name"],
            config=value,
            flows=[flow for key, flow in mapping.flows.items() if mapping.owners[key] == project_id],
            dependency_flows=sources,
        )

    def skill_pack(project_id):
        project = mapping.project(project_id, expected_type="skill-pack")
        definitions = []
        for skill in skill_definitions((project["project_config"] or {}).get("skills", [])):
            value = skill.model_dump(mode="json")
            value["tool_packs"] = [
                pack(str(ref.project_id)).reference.model_dump(mode="json") for ref in skill.tool_packs
            ]
            definitions.append(value)
        return skill_pack_manifest(UUID(mapping.project_ids[project_id]), project["name"], {"skills": definitions})

    if config.get("agent_flow_id"):
        config["agent_flow_id"] = mapping.flow_ids[config["agent_flow_id"]]
    if "tools" in config:
        config["tools"] = [mapping.flow_ids[item] for item in config["tools"]]
    if kind == "skill-pack":
        config["skills"] = [skill.model_dump(mode="json") for skill in skill_pack(mapping.project_id).skills]
    if "skill_packs" in config:
        config["skill_packs"] = [
            skill_pack(str(ref.project_id)).reference.model_dump(mode="json")
            for ref in skill_pack_references(config["skill_packs"])
        ]
    if "tool_packs" in config:
        config["tool_packs"] = [
            pack(str(ref.project_id)).reference.model_dump(mode="json")
            for ref in tool_pack_references(config["tool_packs"])
        ]
    if "flow_bindings" in config:
        parsed = ProjectFlowBindings.model_validate(config["flow_bindings"])
        for _, binding in parsed.entries():
            original = binding.flow_id
            binding.flow_id = mapping.flow_ids[original]
            binding.revision = flow_revision(mapping.source(original)["data"])
            binding.version_id = mapping.version_ids[original]
            binding.dependencies = dependencies(binding.flow_id)
        # Keep defaults explicit, as in the runtime graph. Omitting them can turn
        # a reviewed 10.0 into the model's integer default 10 on the next save,
        # changing the serialized Agent input without a configuration change.
        config["flow_bindings"] = {
            name: [binding.model_dump() for field, binding in parsed.entries() if field == name]
            if isinstance(value, list)
            else getattr(parsed, name).model_dump()
            if getattr(parsed, name) is not None
            else None
            for name, value in config["flow_bindings"].items()
        }
    if "tool_bindings" in config:
        bindings = {}
        for original in config["tool_bindings"]:
            binding = local_tool_definition(mapping.source(original), sources)
            binding.version_id = mapping.version_ids[original]
            binding.dependencies = dependencies(binding.flow_id)
            bindings[binding.flow_id] = binding.model_dump(mode="json")
        config["tool_bindings"] = bindings
    return config

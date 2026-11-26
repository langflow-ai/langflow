"""Agent Harness preparation through the same authorized context as installed types."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from lfx.base.agents.harness import HarnessRuntimeConfig
from lfx.projects.bindings import reject_recursive_binding
from lfx.projects.dependencies import validate_binding_dependencies
from lfx.projects.flow_slots import BINDING_LABELS, ProjectFlowBindings, validate_project_binding
from lfx.projects.lifecycle import PreparedSave, ProjectConfigError
from lfx.projects.local_tools import local_tool_bindings, local_tool_definition
from lfx.projects.skills import HarnessSkills, skill_pack_references
from lfx.projects.source_resolution import resolve_skill_pack, resolve_sources, resolve_tool_pack
from lfx.projects.tool_packs import FlowDependencyVersion, ToolPackToolBinding, tool_pack_references
from lfx.projects.tools import agent_node_ids

if TYPE_CHECKING:
    from lfx.projects.lifecycle import FlowView, ProjectSaveContext, SaveRequest


@dataclass(frozen=True)
class HarnessPreparation:
    config: dict
    bindings: ProjectFlowBindings
    skills: HarnessSkills
    instruction_target: FlowView | None
    tool_targets: tuple[dict, ...]
    compose_tools: bool


def select_agent_flow(flows: tuple[FlowView, ...], config: dict) -> FlowView | None:
    """Prefer an explicit selection, then a unique marked agent, then a unique graph candidate.

    A2A owns ``flow_type``. Harness selection is saved in the existing project config, so
    choosing an entry flow never reclassifies another flow or changes A2A publication.
    """
    candidates = [flow for flow in flows if len(agent_node_ids(flow.data)) == 1 and not flow.is_component]
    selected = config.get("agent_flow_id")
    if selected is not None:
        for flow in candidates:
            if str(flow.id) == selected:
                return flow
        msg = "Choose an agent flow in this project containing exactly one Agent component."
        raise ProjectConfigError(msg)
    marked = [flow for flow in candidates if flow.flow_type == "agent"]
    choices = marked or candidates
    if len(choices) > 1 or (not choices and any(agent_node_ids(flow.data) for flow in flows)):
        msg = "Choose which flow is the agent before saving the harness."
        raise ProjectConfigError(msg)
    return choices[0] if choices else None


def selected_tools(flows: tuple[FlowView, ...], agent: FlowView | None, value: object) -> tuple[FlowView, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        msg = "Tools must be a list of flow IDs from this project."
        raise ProjectConfigError(msg)
    available = {str(flow.id): flow for flow in flows if not flow.is_component}
    picked = []
    for flow_id in dict.fromkeys(value):
        if flow_id not in available:
            msg = "A selected tool is no longer available in this project."
            raise ProjectConfigError(msg)
        if agent is None:
            msg = "Choose an agent flow before adding tools."
            raise ProjectConfigError(msg)
        if flow_id == str(agent.id):
            msg = "The agent flow cannot call itself as a tool."
            raise ProjectConfigError(msg)
        picked.append(available[flow_id])

    # Refuse a tool that calls back into this agent through other local Run Flow nodes.
    by_name = {flow.name: str(flow.id) for flow in flows}
    pending = [str(flow.id) for flow in picked]
    seen = set()
    while pending:
        current = pending.pop()
        if agent is not None and current == str(agent.id):
            msg = "A selected tool calls back into the agent flow."
            raise ProjectConfigError(msg)
        if current in seen or current not in available:
            continue
        seen.add(current)
        for node in (available[current].data or {}).get("nodes", []):
            data = node.get("data", {})
            if data.get("type") != "RunFlow":
                continue
            template = data.get("node", {}).get("template", {})
            target = template.get("flow_id_selected", {}).get("value") or by_name.get(
                template.get("flow_name_selected", {}).get("value")
            )
            if isinstance(target, str):
                pending.append(target)
    return tuple(picked)


def _definitions(flows):
    return [flow.definition() for flow in flows]


async def _sources(ctx, source):
    return {str(key): value for key, value in (await resolve_sources(ctx, (source,), access="execute")).items()}


async def _pin(ctx, source, label):
    (snapshot,) = await ctx.pin_sources((source.token,), label=label)
    return str(snapshot.reference.version_id)


async def prepare_harness(request: SaveRequest, ctx: ProjectSaveContext) -> PreparedSave:
    previous_config = request.previous_config
    if not request.config and not any(
        (previous_config or {}).get(key) for key in ("flow_bindings", "tool_packs", "tools", "skill_packs")
    ):
        return PreparedSave(deepcopy(request.config))
    clearing_config = request.config is None
    config = deepcopy(request.config or {})
    flows = request.flows
    if not request.config and previous_config:
        config["agent_flow_id"] = previous_config.get("agent_flow_id")
    tools = []
    local_targets = []
    pack_targets = []
    try:
        runtime = HarnessRuntimeConfig.model_validate(config)
    except ProjectConfigError:
        raise
    except ValueError as exc:
        msg = "Invalid harness runtime settings. Check context, compaction, and model-call limits."
        raise ProjectConfigError(msg) from exc
    agent = select_agent_flow(flows, config)
    targets = [agent] if agent else []
    if agent is not None:
        node = next(node for node in agent.data["nodes"] if node["data"].get("type") == "Agent")
        template = node["data"]["node"]["template"]
        unsupported = [
            name
            for name, field in HarnessRuntimeConfig.model_fields.items()
            if name in config and name not in template and getattr(runtime, name) != field.default
        ]
        if unsupported:
            msg = "Update the Agent component on its canvas before configuring context or compaction."
            raise ProjectConfigError(msg)
    if "tools" not in config and not clearing_config and (previous_config or {}).get("tools"):
        config["tools"] = deepcopy(previous_config["tools"])
    if "tools" in config:
        tools = selected_tools(flows, agent, config["tools"])

    try:
        requested = local_tool_bindings(config.get("tool_bindings", {}))
        previous = local_tool_bindings((previous_config or {}).get("tool_bindings", {}))
        local_sources = {}
        local_bindings = {}
        for tool in tools:
            tool_id = str(tool.id)
            resolved_sources = await _sources(ctx, tool)
            if str(agent.id) in resolved_sources:
                msg = "A selected tool calls back into the agent flow."
                raise ValueError(msg)
            definitions = _definitions(resolved_sources.values())
            current = local_tool_definition(_definitions([tool])[0], definitions)
            reviewed = requested.get(tool_id) or previous.get(tool_id)
            if reviewed is not None and reviewed.definition() != current.definition():
                msg = "The local tool changed. Review its definition before saving the harness."
                raise ValueError(msg)
            local_sources[tool_id] = resolved_sources
            local_bindings[tool_id] = current
        for tool in tools:
            binding = local_bindings[str(tool.id)]
            binding.version_id = await _pin(ctx, tool, "Local tool")
            for dependency in binding.dependencies:
                dependency.version_id = await _pin(
                    ctx, local_sources[str(tool.id)][dependency.flow_id], "Local tool dependency"
                )
            local_targets.append({**_definitions([tool])[0], "local_tool": binding.model_dump(mode="json")})
        if tools or "tool_bindings" in config or previous:
            config["tool_bindings"] = {key: value.model_dump(mode="json") for key, value in local_bindings.items()}
    except ProjectConfigError:
        raise
    except (ValueError, KeyError, TypeError) as exc:
        msg = f"Could not configure the selected tools: {exc}"
        raise ProjectConfigError(msg) from exc
    try:
        references = tool_pack_references(config.get("tool_packs", []))
        skill_references = skill_pack_references(config.get("skill_packs", []))
    except ProjectConfigError:
        raise
    except (ValueError, TypeError) as exc:
        raise ProjectConfigError(str(exc)) from exc
    if (references or skill_references) and agent is None:
        msg = "Choose an agent flow before adding capability packs."
        raise ProjectConfigError(msg)
    skill_manifests = []
    for reference in skill_references:
        manifest = await resolve_skill_pack(ctx, reference.project_id, access="execute")
        if manifest.reference != reference:
            msg = "The Skill Pack changed. Review it before saving the harness."
            raise ProjectConfigError(msg)
        skill_manifests.append(manifest)
    skills = HarnessSkills(packs=tuple(skill_manifests), global_tool_pack_ids=tuple(r.project_id for r in references))
    all_references = {ref.project_id: ref for ref in references}
    for manifest in skill_manifests:
        for skill in manifest.skills:
            for ref in skill.tool_packs:
                if ref.project_id in all_references and all_references[ref.project_id] != ref:
                    msg = "The selected skills require different revisions of one Tool Pack."
                    raise ProjectConfigError(msg)
                all_references[ref.project_id] = ref
    resolved = []
    for reference in all_references.values():
        manifest, exports = await resolve_tool_pack(ctx, reference.project_id, access="execute")
        if manifest.reference != reference:
            msg = "The tool pack changed. Review its exports before saving the harness."
            raise ProjectConfigError(msg)
        resolved.append((manifest, {export.id: export for export in exports.values()}))
    for manifest, exports in resolved:
        for export in manifest.tools:
            source = exports[export.flow_id]
            try:
                reject_recursive_binding(
                    [
                        {"id": str(item.id), "name": item.name, "data": item.data}
                        for item in [*flows, *exports.values()]
                    ],
                    str(source.id),
                    str(agent.id),
                )
            except ProjectConfigError:
                raise
            except ValueError as exc:
                raise ProjectConfigError(str(exc)) from exc
            version_id = await _pin(ctx, source, "Tool Pack")
            dependency_versions = tuple(
                [
                    FlowDependencyVersion(
                        flow=dependency,
                        version_id=UUID(await _pin(ctx, exports[dependency.flow_id], "Tool Pack dependency")),
                    )
                    for dependency in export.dependencies
                ]
            )
            binding = ToolPackToolBinding(
                reference=manifest.reference,
                tool=export,
                version_id=UUID(version_id),
                dependency_versions=dependency_versions,
            )
            pack_targets.append(
                {
                    "id": str(source.id),
                    "name": source.name,
                    "data": source.data,
                    "tool_pack": binding.model_dump(mode="json"),
                }
            )
    if "tool_packs" in config:
        config["tool_packs"] = [reference.model_dump(mode="json") for reference in references]
    if "skill_packs" in config:
        config["skill_packs"] = [reference.model_dump(mode="json") for reference in skill_references]
    if agent is not None:
        config["agent_flow_id"] = str(agent.id)
    try:
        bindings = ProjectFlowBindings.model_validate(config.get("flow_bindings", {}))
    except ProjectConfigError:
        raise
    except ValueError as exc:
        msg = "Invalid flow bindings. Choose compatible harness outputs and valid binding settings."
        raise ProjectConfigError(msg) from exc
    sources = {str(flow.id): flow for flow in flows if not flow.is_component}

    binding_sources = {}
    for field_name, binding in bindings.entries():
        try:
            source = sources.get(binding.flow_id)
            if source is None or agent is None:
                msg = "Choose an agent and a compatible flow in this project."
                raise ValueError(msg)
            reject_recursive_binding(
                [{"id": str(flow.id), "name": flow.name, "data": flow.data} for flow in flows],
                str(source.id),
                str(agent.id),
            )
            validate_project_binding(field_name, source.data, binding)
            resolved_sources = await _sources(ctx, source)
            validate_binding_dependencies(binding, _definitions(resolved_sources.values()))
            binding_sources[binding.flow_id] = resolved_sources
        except ProjectConfigError:
            raise
        except (ValueError, KeyError, TypeError) as exc:
            msg = f"Could not bind {BINDING_LABELS[field_name]}: {exc}"
            raise ProjectConfigError(msg) from exc
    # Validate the entire set before creating any required source snapshots.
    for field_name, binding in bindings.entries():
        binding.version_id = await _pin(ctx, sources[binding.flow_id], field_name)
        for dependency in binding.dependencies:
            dependency.version_id = await _pin(ctx, binding_sources[binding.flow_id][dependency.flow_id], field_name)
    if "flow_bindings" in config:
        config["flow_bindings"] = bindings.model_dump(exclude_unset=True, exclude_none=True)
    instruction_binding = bindings.system_prompt
    instruction_target = sources.get(instruction_binding.flow_id) if instruction_binding else None
    state = HarnessPreparation(
        config,
        bindings,
        skills,
        instruction_target,
        tuple(local_targets + pack_targets),
        bool(
            "tools" in config
            or "tool_packs" in config
            or "skill_packs" in config
            or (previous_config or {}).get("tool_packs")
            or (previous_config or {}).get("skill_packs")
            or clearing_config
        ),
    )
    return PreparedSave(None if clearing_config else config, tuple(flow.id for flow in targets), state)

"""Resolve reviewed built-in sources through authorized, host-independent reads."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal
from uuid import UUID

from lfx.projects.dependencies import binding_dependencies, flow_references, validate_binding_dependencies
from lfx.projects.lifecycle import FlowSelector, PreparedSave, ProjectConfigError, SourceVersionReference
from lfx.projects.skills import skill_pack_manifest
from lfx.projects.tool_packs import ToolPackToolBinding, exported_flow_ids, tool_pack_manifest

if TYPE_CHECKING:
    from lfx.projects.lifecycle import FlowView, ProjectSaveContext, SaveRequest

MAX_DEPENDENCY_FLOWS = 500


async def resolve_sources(
    ctx: ProjectSaveContext,
    roots: tuple[FlowView, ...],
    *,
    access: Literal["read", "execute"] = "read",
    resolving: frozenset[UUID] = frozenset(),
) -> dict[UUID, FlowView]:
    """Check static dependencies and nested pack reviews without executing components."""
    available = {}
    pending = list(roots)
    while pending:
        source = pending.pop()
        if source.id in available:
            continue
        # A caller-supplied root view is not evidence of EXECUTE permission.
        source = await ctx.read_flow(FlowSelector(id=source.id), access=access)
        available[source.id] = source
        if len(available) > MAX_DEPENDENCY_FLOWS:
            msg = "A harness customization cannot depend on more than 500 flows."
            raise ProjectConfigError(msg)
        for node in source.data.get("nodes", []):
            value = (node.get("data", {}).get("_harness_tool") or {}).get("tool_pack")
            if value:
                binding = ToolPackToolBinding.model_validate(value)
                manifest, _ = await resolve_tool_pack(
                    ctx, binding.reference.project_id, access=access, resolving=resolving
                )
                if manifest.reference != binding.reference or binding.tool not in manifest.tools:
                    msg = "A nested Tool Pack changed. Review its reference before binding this flow."
                    raise ProjectConfigError(msg)
        for reference in flow_references(source.data):
            selector = (
                FlowSelector(id=UUID(reference.flow_id)) if reference.flow_id else FlowSelector(name=reference.name)
            )
            dependency = await ctx.read_flow(selector, access=access)
            if dependency.id not in available:
                pending.append(dependency)
    definitions = [source.definition() for source in available.values()]
    for root in roots:
        binding_dependencies(str(root.id), definitions)
    return available


async def resolve_tool_pack(
    ctx: ProjectSaveContext,
    project_id: UUID,
    *,
    access: Literal["read", "execute"] = "read",
    resolving: frozenset[UUID] = frozenset(),
):
    if project_id in resolving:
        msg = "The Tool Packs contain a recursive project reference."
        raise ProjectConfigError(msg)
    project = await ctx.read_project(project_id, expected_type="tool-pack")
    roots = []
    for flow_id in exported_flow_ids(project.config):
        source = await ctx.read_flow(FlowSelector(id=flow_id), access=access)
        if source.project_id != project.id:
            msg = "An exported tool is no longer available in its Tool Pack."
            raise ProjectConfigError(msg)
        roots.append(source)
    sources = await resolve_sources(ctx, tuple(roots), access=access, resolving=resolving | {project_id})
    manifest = tool_pack_manifest(
        project_id=project.id,
        name=project.name,
        config=project.config,
        flows=[source.definition() for source in roots],
        dependency_flows=[source.definition() for source in sources.values()],
    )
    return manifest, sources


async def resolve_skill_pack(ctx: ProjectSaveContext, project_id: UUID, *, access="read"):
    project = await ctx.read_project(project_id, expected_type="skill-pack")
    manifest = skill_pack_manifest(project.id, project.name, project.config)
    reviewed = {}
    for skill in manifest.skills:
        for reference in skill.tool_packs:
            if reference.project_id not in reviewed:
                tools, _ = await resolve_tool_pack(ctx, reference.project_id, access=access)
                reviewed[reference.project_id] = tools.reference
            if reviewed[reference.project_id] != reference:
                msg = f"A Tool Pack used by skill '{skill.name}' changed. Review it in the Skill Pack."
                raise ProjectConfigError(msg)
    return manifest


async def prepare_tool_pack(request: SaveRequest, ctx: ProjectSaveContext) -> PreparedSave:
    try:
        manifest, _ = await resolve_tool_pack(ctx, request.project.id)
        config = (
            None if request.config is None else {**request.config, "tools": [str(t.flow_id) for t in manifest.tools]}
        )
        return PreparedSave(config)
    except ProjectConfigError:
        raise
    except (ValueError, KeyError, TypeError) as exc:
        msg = "Could not export the selected tools. Review their definitions."
        raise ProjectConfigError(msg) from exc


async def prepare_skill_pack(request: SaveRequest, ctx: ProjectSaveContext) -> PreparedSave:
    try:
        manifest = await resolve_skill_pack(ctx, request.project.id)
        config = (
            None
            if request.config is None
            else {**request.config, "skills": [skill.model_dump(mode="json") for skill in manifest.skills]}
        )
        return PreparedSave(config)
    except ProjectConfigError:
        raise
    except (ValueError, KeyError, TypeError) as exc:
        msg = "Invalid Skill Pack. Review its skill definitions."
        raise ProjectConfigError(msg) from exc


async def prepare_eval_suite(request: SaveRequest, ctx: ProjectSaveContext) -> PreparedSave:
    from lfx.projects.builtin_slots import SCORER
    from lfx.projects.evaluations import EvalSuiteConfig

    if request.config is None:
        return PreparedSave(None)
    try:
        suite = EvalSuiteConfig.model_validate(request.config)
        binding = suite.scorer
        if binding is not None:
            if (request.previous_config or {}).get("scorer") == binding.model_dump(mode="json") and binding.version_id:
                definitions = []
                for item in [binding, *binding.dependencies]:
                    if not item.version_id:
                        msg = "The scorer snapshots are incomplete. Review and save the scorer."
                        raise ProjectConfigError(msg)
                    saved = await ctx.read_saved_source(
                        SourceVersionReference(UUID(item.flow_id), UUID(item.version_id), item.revision)
                    )
                    definitions.append(
                        {
                            "id": item.flow_id,
                            "name": getattr(item, "name", ""),
                            "description": getattr(item, "description", ""),
                            "data": saved.data,
                        }
                    )
                validate_binding_dependencies(binding, definitions)
            else:
                root = await ctx.read_flow(FlowSelector(id=UUID(binding.flow_id)), access="execute")
                SCORER.validate_binding(root.data, binding)
                sources = await resolve_sources(ctx, (root,), access="execute")
                validate_binding_dependencies(binding, [source.definition() for source in sources.values()])
                items = [binding, *binding.dependencies]
                snapshots = await ctx.pin_sources(
                    tuple(sources[UUID(item.flow_id)].token for item in items), label="scorer"
                )
                for item, snapshot in zip(items, snapshots, strict=True):
                    item.version_id = str(snapshot.reference.version_id)
        return PreparedSave(suite.model_dump(mode="json"))
    except ProjectConfigError:
        raise
    except (ValueError, KeyError, TypeError) as exc:
        msg = "Invalid evaluation configuration. Review the cases and scorer definition."
        raise ProjectConfigError(msg) from exc

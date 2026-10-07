"""The type interface works with a host-independent in-memory adapter."""

from copy import deepcopy
from dataclasses import replace
from uuid import UUID, uuid4

import pytest
from lfx.projects import get_project_type, register_project_type
from lfx.projects.bindings import flow_revision
from lfx.projects.builtins import FlowsType
from lfx.projects.lifecycle import (
    FlowView,
    ProjectConfigError,
    ProjectView,
    SaveRequest,
    SourceSnapshot,
    SourceVersionReference,
)
from lfx.projects.source_resolution import resolve_sources, resolve_tool_pack

from tests.unit.projects.test_tool_packs import tool  # noqa: F401


class MemoryContext:
    def __init__(self, projects=(), flows=()):
        self.projects = {project.id: deepcopy(project) for project in projects}
        self.flows = {flow.id: deepcopy(flow) for flow in flows}
        self.reads = []
        self.snapshots = {}

    async def read_project(self, project_id, *, expected_type):
        project = self.projects[project_id]
        if project.project_type != expected_type:
            msg = "Wrong type"
            raise ProjectConfigError(msg)
        return deepcopy(project)

    async def read_flow(self, selector, *, access):
        self.reads.append((selector.id, access))
        return deepcopy(self.flows[selector.id])

    async def pin_sources(self, tokens, *, label):  # noqa: ARG002
        result = []
        for token in tokens:
            flow = next(flow for flow in self.flows.values() if flow.token == token)
            assert (flow.id, "execute") in self.reads
            reference = SourceVersionReference(flow.id, uuid4(), flow.revision)
            snapshot = SourceSnapshot(reference, deepcopy(flow.data))
            self.snapshots[reference.version_id] = snapshot
            result.append(snapshot)
        return tuple(result)

    async def read_saved_source(self, reference):
        return deepcopy(self.snapshots[reference.version_id])


def view(project, definition):
    return FlowView(
        UUID(definition["id"]),
        project.id,
        definition["name"],
        definition.get("description", ""),
        deepcopy(definition["data"]),
        is_component=False,
        flow_type="generic",
        locked=False,
        revision=flow_revision(definition["data"]),
        token=uuid4().hex,
    )


async def test_tool_pack_hook_matches_manifest_without_writing_sources(tool):  # noqa: F811
    project = ProjectView(uuid4(), "Tools", "tool-pack", {"tools": [tool["id"], tool["id"]]})
    source = view(project, tool)
    ctx = MemoryContext((project,), (source,))
    request = SaveRequest(project, "replace", project.config, None, (source,))
    result = await get_project_type("tool-pack").save_config(request, ctx)
    assert result.config == {"tools": [tool["id"]]}
    assert result.target_flow_ids == ()
    assert ctx.snapshots == {}
    assert all(access == "read" for _, access in ctx.reads)


@pytest.mark.parametrize("kind", ["tool-pack", "skill-pack", "eval-suite", "flows"])
async def test_builtin_clear_is_distinct_from_empty_config(kind):
    project = ProjectView(uuid4(), "Cleared", kind, None)
    ctx = MemoryContext((project,))
    request = SaveRequest(project, "clear", None, {"old": "config"})
    assert (await get_project_type(kind).save_config(request, ctx)).config is None
    empty = replace(project, config={})
    ctx.projects[empty.id] = empty
    prepared = await get_project_type(kind).save_config(SaveRequest(empty, "replace", {}, None), ctx)
    assert isinstance(prepared.config, dict)


async def test_pack_rejects_export_from_different_project(tool):  # noqa: F811
    project = ProjectView(uuid4(), "Tools", "tool-pack", {"tools": [tool["id"]]})
    source = replace(view(project, tool), project_id=uuid4())
    with pytest.raises(ProjectConfigError, match="no longer available"):
        await resolve_tool_pack(MemoryContext((project,), (source,)), project.id)


async def test_dependencies_get_execute_reads_and_cycles_are_rejected(tool):  # noqa: F811
    project = ProjectView(uuid4(), "Tools", "tool-pack", {})
    root = view(project, tool)
    child = replace(root, id=uuid4(), token=uuid4().hex, name="Nested")

    def calls(source):
        return {
            "nodes": [
                {
                    "id": "call",
                    "data": {"type": "RunFlow", "node": {"template": {"flow_id_selected": {"value": str(source.id)}}}},
                }
            ],
            "edges": [],
        }

    root = replace(root, data=calls(child))
    ctx = MemoryContext((project,), (root, child))
    resolved = await resolve_sources(ctx, (root,), access="execute")
    assert set(resolved) == {root.id, child.id}
    assert (root.id, "execute") in ctx.reads
    assert (child.id, "execute") in ctx.reads
    ctx.flows[child.id] = replace(child, data=calls(root))
    with pytest.raises(ValueError, match="recursive"):
        await resolve_sources(ctx, (root,), access="execute")


@pytest.mark.parametrize("hook", ["save_config", "compose"])
def test_registration_rejects_wrong_hook_execution_model(hook):
    class InvalidType(FlowsType):
        name = "invalid-lifecycle"

    if hook == "save_config":
        InvalidType.save_config = lambda _self, _request, _ctx: None
    else:

        async def asynchronous(_self, _prepared, _ctx):
            return ()

        InvalidType.compose = asynchronous
    with pytest.raises(TypeError, match=hook):
        register_project_type(InvalidType)

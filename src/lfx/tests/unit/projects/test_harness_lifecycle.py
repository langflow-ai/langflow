"""Harness preparation works through detached records without a Langflow host."""

from copy import deepcopy
from dataclasses import replace
from uuid import uuid4

import pytest
from lfx.components.models_and_agents.agent import AgentComponent
from lfx.projects import get_project_type
from lfx.projects.lifecycle import (
    CompositionContext,
    ProjectConfigError,
    ProjectResourceUnavailableError,
    ProjectView,
    SaveRequest,
)

from tests.unit.projects.test_lifecycle import MemoryContext, view
from tests.unit.projects.test_tool_packs import tool  # noqa: F401


def harness():
    project = ProjectView(uuid4(), "Research", "agent-harness", {})
    agent = view(
        project,
        {
            "id": str(uuid4()),
            "name": "Agent",
            "data": {
                "nodes": [AgentComponent().to_frontend_node()],
                "edges": [],
            },
        },
    )
    return project, agent


async def test_preparation_selects_one_agent_and_does_not_mutate_inputs():
    project, agent = harness()
    other = replace(agent, id=uuid4(), name="Other")
    config = {"agent_flow_id": str(agent.id), "system_prompt": "Research carefully"}
    request = SaveRequest(project, "replace", config, None, (agent, other))
    before = deepcopy(request)
    prepared = await get_project_type("agent-harness").save_config(request, MemoryContext())
    assert prepared.target_flow_ids == (agent.id,)
    assert prepared.config == config
    assert request == before
    with pytest.raises(ProjectConfigError, match="Choose which flow"):
        await get_project_type("agent-harness").save_config(
            replace(request, config={"system_prompt": "Ambiguous"}), MemoryContext()
        )


async def test_local_tool_is_reviewed_and_pinned_through_context(tool):  # noqa: F811
    project, agent = harness()
    source = view(project, tool)
    ctx = MemoryContext((project,), (agent, source))
    request = SaveRequest(project, "replace", {"tools": [str(source.id)]}, None, (agent, source))
    prepared = await get_project_type("agent-harness").save_config(request, ctx)
    binding = prepared.config["tool_bindings"][str(source.id)]
    assert binding["version_id"] in {str(key) for key in ctx.snapshots}
    assert (source.id, "execute") in ctx.reads
    assert prepared.state.tool_targets[0]["local_tool"] == binding
    changed = replace(source, description="Changed callable contract")
    ctx.flows[source.id] = changed
    with pytest.raises(ProjectConfigError, match="local tool changed"):
        await get_project_type("agent-harness").save_config(
            replace(request, previous_config=prepared.config, flows=(agent, changed)), ctx
        )


async def test_clear_keeps_previous_agent_selection_and_removes_owned_tools(tool):  # noqa: F811
    project, agent = harness()
    other = replace(agent, id=uuid4())
    previous = {"agent_flow_id": str(agent.id), "tools": [tool["id"]]}
    prepared = await get_project_type("agent-harness").save_config(
        SaveRequest(project, "clear", None, previous, (agent, other)), MemoryContext()
    )
    assert prepared.config is None
    assert prepared.target_flow_ids == (agent.id,)
    assert prepared.state.tool_targets == ()
    assert prepared.state.compose_tools is True


async def test_execute_denial_keeps_its_resource_error(tool):  # noqa: F811
    class DeniedContext(MemoryContext):
        async def read_flow(self, selector, *, access):
            if access == "execute":
                msg = "Source unavailable"
                raise ProjectResourceUnavailableError(msg)
            return await super().read_flow(selector, access=access)

    project, agent = harness()
    source = view(project, tool)
    ctx = DeniedContext((project,), (source,))
    with pytest.raises(ProjectResourceUnavailableError):
        await get_project_type("agent-harness").save_config(
            SaveRequest(project, "replace", {"tools": [str(source.id)]}, None, (agent, source)), ctx
        )
    assert ctx.snapshots == {}


async def test_composition_is_pure_and_preserves_independent_canvas_edits():
    project, agent = harness()
    definition = get_project_type("agent-harness")
    prepared = await definition.save_config(
        SaveRequest(project, "replace", {"system_prompt": "From the form"}, None, (agent,)), MemoryContext()
    )
    before = deepcopy(agent)
    (first,) = definition.compose(prepared, CompositionContext(project, (agent,)))
    assert agent == before
    assert first.data["nodes"][0]["data"]["node"]["template"]["system_prompt"]["value"] == "From the form"
    first.data["nodes"][0]["data"]["node"]["template"]["system_prompt"]["value"] = "From the canvas"
    changed = replace(agent, data=first.data)
    next_save = await definition.save_config(
        SaveRequest(project, "replace", {"system_prompt": "Updated form"}, prepared.config, (changed,)), MemoryContext()
    )
    (second,) = definition.compose(
        next_save, CompositionContext(project, (changed,), {str(agent.id): first.applied_values})
    )
    assert second.fields_skipped == 1
    assert second.data["nodes"][0]["data"]["node"]["template"]["system_prompt"]["value"] == "From the canvas"
    assert second.applied_values == first.applied_values

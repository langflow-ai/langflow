"""Project Context bindings retain ownership and remap mixed runtime dependencies."""

import json
from copy import deepcopy

import pytest
from lfx.projects.baselines import context_baseline, hook_baseline
from lfx.projects.bindings import flow_revision, reject_recursive_binding
from lfx.projects.context import CONTEXT_ORIGIN, ContextBinding, compose_context, validate_context_binding
from lfx.projects.flow_slots import ProjectFlowBindings, flow_runtime_bindings, remap_runtime_bindings
from lfx.projects.hooks import compose_hooks, validate_hook_binding

from tests.unit.projects.test_hook_bindings import binding_for


def agent_data():
    return {
        "nodes": [
            {
                "id": "agent",
                "data": {
                    "type": "Agent",
                    "node": {
                        "template": {
                            "hook_bindings": {"value": "[]", "override_skip": True},
                            "context_binding": {"value": "", "override_skip": True},
                        }
                    },
                },
            }
        ],
        "edges": [],
    }


def context_binding(source, flow_id="source"):
    node = source["nodes"][-1]
    return ContextBinding(flow_id=flow_id, node_id=node["id"], output_name="context", revision=flow_revision(source))


def compose(data, binding):
    return compose_context(data, project_id="project", agent_id="agent", binding=binding)


def test_context_reconciles_idempotently_and_removes_only_owned_value():
    original = agent_data()
    binding = context_binding(context_baseline()["data"])
    configured = compose(original, binding)
    assert compose(configured, binding) == configured
    assert original == agent_data()
    assert compose(configured, None) == original
    manual = deepcopy(configured)
    manual["nodes"][0]["data"].pop(CONTEXT_ORIGIN)
    assert compose(manual, None) == manual


@pytest.mark.parametrize("defect", ["edited", "manual", "connected", "foreign", "old_agent", "non_text"])
def test_context_binding_rejects_canvas_conflicts_without_mutation(defect):
    binding = context_binding(context_baseline()["data"])
    data = compose(agent_data(), binding)
    node = data["nodes"][0]["data"]
    if defect == "old_agent":
        node["node"]["template"].pop("context_binding")
    elif defect == "non_text":
        node["node"]["template"]["context_binding"]["value"] = {"manual": True}
    elif defect == "foreign":
        node[CONTEXT_ORIGIN]["project_id"] = "other"
    elif defect == "connected":
        data["edges"] = [{"target": "agent", "data": {"targetHandle": {"fieldName": "context_binding"}}}]
    else:
        node["node"]["template"]["context_binding"]["value"] = '{"manual":true}'
        if defect == "manual":
            node.pop(CONTEXT_ORIGIN)
    before = deepcopy(data)
    with pytest.raises((ValueError, TypeError), match="canvas"):
        compose(data, binding)
    assert data == before


def test_project_bindings_parse_context_with_instructions_and_hooks():
    context = context_binding(context_baseline()["data"]).model_dump()
    hook = binding_for(hook_baseline()["data"]).model_dump()
    parsed = ProjectFlowBindings.model_validate({"context_strategy": context, "hooks": [hook]})
    assert len(parsed.entries()) == 2
    assert parsed.context_strategy.timeout_seconds == 30
    with pytest.raises(ValueError, match="context_strategy"):
        ProjectFlowBindings.model_validate({"context_strategy": [context]})
    with pytest.raises(ValueError, match="context_strategy"):
        ProjectFlowBindings.model_validate({"context_strategy": {**context, "timeout_seconds": 0}})


@pytest.mark.parametrize("order", ["context_to_hook", "hook_to_context"])
def test_mixed_nested_runtime_import_updates_children_before_parent_revisions(order):
    from lfx.components.models_and_agents.agent import AgentComponent

    leaf = hook_baseline()["data"] if order == "context_to_hook" else context_baseline()["data"]
    outer = context_baseline()["data"] if order == "context_to_hook" else hook_baseline()["data"]
    # A real nested Agent node makes static validation inspect its declared required inputs.
    node = AgentComponent().to_frontend_node()
    node["id"] = node["data"]["id"] = "agent"
    node["data"]["node"]["template"]["model"]["value"] = [{"name": "test model"}]
    nested = {"nodes": [node], "edges": []}
    if order == "context_to_hook":
        nested = compose_hooks(
            nested,
            project_id="project",
            agent_id="agent",
            bindings=[
                binding_for(leaf).model_copy(update={"flow_id": "leaf"}),
            ],
        )
        parent_binding = context_binding(outer, "outer")
    else:
        nested = compose(nested, context_binding(leaf, "leaf"))
        parent_binding = binding_for(outer).model_copy(update={"flow_id": "outer"})
    outer["nodes"].extend(nested["nodes"])
    parent_binding.revision = flow_revision(outer)
    parent = (
        compose(agent_data(), parent_binding)
        if order == "context_to_hook"
        else compose_hooks(
            agent_data(),
            project_id="project",
            agent_id="agent",
            bindings=[parent_binding],
        )
    )
    flows = {"parent": parent, "outer": outer, "leaf": leaf}
    remap_runtime_bindings(flows, {key: f"new-{key}" for key in flows}, "new-project")
    for data, source, target in [(parent, outer, "new-outer"), (nested, leaf, "new-leaf")]:
        field_name, binding = flow_runtime_bindings(data)[0]
        assert binding.flow_id == target
        assert binding.version_id is None
        if field_name == "hooks":
            validate_hook_binding(source, binding)
        else:
            validate_context_binding(source, binding)
            origin = data["nodes"][0]["data"][CONTEXT_ORIGIN]
            assert origin == {"project_id": "new-project", "binding": binding.model_dump()}


def test_context_references_participate_in_recursion_checks_and_import_guards():
    binding = context_binding(context_baseline()["data"])
    recursive = compose(agent_data(), binding)
    with pytest.raises(ValueError, match="recursive"):
        reject_recursive_binding([{"id": "source", "name": "source", "data": recursive}], "source", "other")
    with pytest.raises(ValueError, match="recursive"):
        remap_runtime_bindings({"source": recursive}, {"source": "new"}, "project")
    with pytest.raises(ValueError, match="archive"):
        remap_runtime_bindings({"agent": recursive}, {"agent": "new"}, "project")


def test_runtime_parser_accepts_empty_context_sentinels_without_executing_code():
    data = agent_data()
    template = data["nodes"][0]["data"]["node"]["template"]
    template["code"] = {"value": "raise RuntimeError('not executed')"}
    for value in ["", " ", "null", "{}"]:
        template["context_binding"]["value"] = value
        assert flow_runtime_bindings(data) == []
        assert compose(data, context_binding(context_baseline()["data"]))
    template["context_binding"]["value"] = json.dumps({"flow_id": "incomplete"})
    with pytest.raises(ValueError, match="context_strategy"):
        flow_runtime_bindings(data)

"""Binding composition preserves canvas ownership and needs no Langflow installation."""

import json
from copy import deepcopy

import pytest
from lfx.base.agents.hooks import HookBinding
from lfx.projects.baselines import hook_baseline
from lfx.projects.bindings import flow_revision, reject_recursive_binding
from lfx.projects.flow_slots import ProjectFlowBindings, binding_outputs
from lfx.projects.hooks import HOOK_ORIGIN, compose_hooks, remap_flow_hooks, validate_hook_binding


def agent_data():
    return {
        "nodes": [
            {
                "id": "agent",
                "data": {
                    "type": "Agent",
                    "node": {"template": {"hook_bindings": {"value": "[]", "override_skip": True}}},
                },
            }
        ],
        "edges": [],
    }


def binding_for(source):
    output = binding_outputs("hooks", source)[0]
    return HookBinding(
        flow_id="source",
        revision=flow_revision(source),
        on_event="before_llm_call",
        **{key: output[key] for key in ("node_id", "output_name")},
    )


def compose(data, bindings):
    return compose_hooks(data, project_id="project", agent_id="agent", bindings=bindings)


def test_hooks_reconcile_idempotently_and_remove_only_owned_configuration():
    original = agent_data()
    bindings = [binding_for(hook_baseline()["data"])]
    configured = compose(original, bindings)
    assert compose(configured, bindings) == configured
    assert original == agent_data()
    cleared = compose(configured, [])
    assert cleared == original


@pytest.mark.parametrize("defect", ["edited", "manual", "connected", "foreign", "old_agent"])
def test_hook_bindings_do_not_replace_canvas_edits(defect):
    bindings = [binding_for(hook_baseline()["data"])]
    data = compose(agent_data(), bindings)
    node = data["nodes"][0]["data"]
    if defect == "old_agent":
        node["node"]["template"].pop("hook_bindings")
    elif defect == "foreign":
        node[HOOK_ORIGIN]["project_id"] = "other"
    elif defect == "connected":
        data["edges"] = [{"target": "agent", "data": {"targetHandle": {"fieldName": "hook_bindings"}}}]
    else:
        node["node"]["template"]["hook_bindings"]["value"] = "[]" if defect == "edited" else '[{"custom":true}]'
        if defect == "manual":
            node.pop(HOOK_ORIGIN)
    before = deepcopy(data)
    with pytest.raises((ValueError, TypeError), match="canvas"):
        compose(data, bindings)
    assert data == before


def test_static_hook_discovery_does_not_execute_saved_code():
    source = hook_baseline()["data"]
    source["nodes"][-1]["data"]["node"]["template"]["code"]["value"] = "raise RuntimeError('not executed')"
    assert binding_outputs("hooks", source)[0]["output_name"] == "decision"


def test_hook_references_participate_in_recursion_checks():
    source = hook_baseline()["data"]
    hooked_agent = compose(agent_data(), [binding_for(source)])
    flows = [{"id": "source", "name": "source", "data": hooked_agent}]
    with pytest.raises(ValueError, match="recursive"):
        reject_recursive_binding(flows, "source", "other")


def test_import_remaps_runtime_and_origin_together():
    source = hook_baseline()["data"]
    agent = compose(agent_data(), [binding_for(source)])
    remap_flow_hooks({"agent": agent, "source": source}, {"agent": "new-agent", "source": "new-source"}, "new-project")
    node = agent["nodes"][0]["data"]
    bindings = json.loads(node["node"]["template"]["hook_bindings"]["value"])
    assert node[HOOK_ORIGIN] == {"project_id": "new-project", "bindings": bindings}
    assert bindings[0]["flow_id"] == "new-source"
    validate_hook_binding(source, HookBinding.model_validate(bindings[0]))


def test_nested_hook_import_updates_parent_revisions_after_children():
    from lfx.components.models_and_agents.agent import AgentComponent

    leaf = hook_baseline()["data"]
    node = AgentComponent().to_frontend_node()
    node["id"] = node["data"]["id"] = "agent"
    node["data"]["node"]["template"]["model"]["value"] = [{"name": "test model"}]
    nested = compose({"nodes": [node], "edges": []}, [binding_for(leaf).model_copy(update={"flow_id": "leaf"})])
    outer = hook_baseline()["data"]
    outer["nodes"].extend(nested["nodes"])
    parent = compose(agent_data(), [binding_for(outer).model_copy(update={"flow_id": "outer"})])
    flows = {"parent": parent, "outer": outer, "leaf": leaf}
    remap_flow_hooks(flows, {key: f"new-{key}" for key in flows}, "new-project")
    for data, source, target in [(parent, outer, "new-outer"), (nested, leaf, "new-leaf")]:
        value = json.loads(data["nodes"][0]["data"]["node"]["template"]["hook_bindings"]["value"])[0]
        assert value["flow_id"] == target
        validate_hook_binding(source, HookBinding.model_validate(value))


@pytest.mark.parametrize("value", [[], {"hooks": {}}, {"compaction": {}}, {"hooks": [{"on_event": "unknown"}]}])
def test_project_binding_shape_rejects_unsupported_or_malformed_values(value):
    with pytest.raises(ValueError, match="validation error"):
        ProjectFlowBindings.model_validate(value)

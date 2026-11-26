"""Compaction bindings preserve canvas ownership and remap mixed compositions."""

import json
from copy import deepcopy

import pytest
from lfx.projects.baselines import compaction_baseline, context_baseline, hook_baseline, permission_baseline
from lfx.projects.bindings import flow_revision, reject_recursive_binding
from lfx.projects.compaction import COMPACTION_ORIGIN, CompactionBinding, compose_compaction
from lfx.projects.context import compose_context
from lfx.projects.flow_slots import (
    ProjectFlowBindings,
    binding_outputs,
    flow_runtime_bindings,
    remap_runtime_bindings,
    validate_project_binding,
)
from lfx.projects.hooks import compose_hooks
from lfx.projects.permissions import compose_permission

from tests.unit.projects.test_context_bindings import agent_data as context_agent_data


def agent_data():
    data = context_agent_data()
    data["nodes"][0]["data"]["node"]["template"]["compaction_binding"] = {"value": "", "override_skip": True}
    data["nodes"][0]["data"]["node"]["template"]["permission_binding"] = {"value": "", "override_skip": True}
    return data


def binding_for(source, flow_id="source"):
    output = binding_outputs("compaction", source)[0]
    return CompactionBinding(
        flow_id=flow_id,
        revision=flow_revision(source),
        trigger_tokens=1200,
        timeout_seconds=2.5,
        **{key: output[key] for key in ("node_id", "output_name")},
    )


def compose(data, binding):
    return compose_compaction(data, project_id="project", agent_id="agent", binding=binding)


def test_compaction_reconciles_and_clears_only_owned_values():
    original = agent_data()
    binding = binding_for(compaction_baseline()["data"])
    configured = compose(original, binding)
    assert compose(configured, binding) == configured
    assert original == agent_data()
    assert compose(configured, None) == original
    manual = deepcopy(configured)
    manual["nodes"][0]["data"].pop(COMPACTION_ORIGIN)
    assert compose(manual, None) == manual


@pytest.mark.parametrize("defect", ["edited", "manual", "connected", "foreign", "old_agent", "non_text"])
def test_compaction_conflicts_do_not_mutate_the_canvas(defect):
    binding = binding_for(compaction_baseline()["data"])
    data = compose(agent_data(), binding)
    node = data["nodes"][0]["data"]
    template = node["node"]["template"]
    if defect == "old_agent":
        template.pop("compaction_binding")
    elif defect == "non_text":
        template["compaction_binding"]["value"] = {"manual": True}
    elif defect == "foreign":
        node[COMPACTION_ORIGIN]["project_id"] = "other"
    elif defect == "connected":
        data["edges"] = [{"target": "agent", "data": {"targetHandle": {"fieldName": "compaction_binding"}}}]
    else:
        template["compaction_binding"]["value"] = '{"manual":true}'
        if defect == "manual":
            node.pop(COMPACTION_ORIGIN)
    before = deepcopy(data)
    with pytest.raises((ValueError, TypeError), match="canvas"):
        compose(data, binding)
    assert data == before


def test_compaction_references_participate_in_recursion_and_archive_guards():
    binding = binding_for(compaction_baseline()["data"])
    recursive = compose(agent_data(), binding)
    with pytest.raises(ValueError, match="recursive"):
        reject_recursive_binding([{"id": "source", "name": "source", "data": recursive}], "source", "other")
    with pytest.raises(ValueError, match="recursive"):
        remap_runtime_bindings({"source": recursive}, {"source": "new"}, "project")
    with pytest.raises(ValueError, match="archive"):
        remap_runtime_bindings({"agent": recursive}, {"agent": "new"}, "project")


def test_empty_compaction_values_are_accepted_without_executing_code():
    data = agent_data()
    template = data["nodes"][0]["data"]["node"]["template"]
    template["code"] = {"value": "raise RuntimeError('not executed')"}
    for value in ["", " ", "null", "{}"]:
        template["compaction_binding"]["value"] = value
        assert flow_runtime_bindings(data) == []
        assert compose(data, binding_for(compaction_baseline()["data"]))
    template["compaction_binding"]["value"] = json.dumps({"flow_id": "incomplete"})
    with pytest.raises(ValueError, match="compaction"):
        flow_runtime_bindings(data)


@pytest.mark.parametrize("value", [False, 0, [], {}])
def test_non_text_empty_values_cannot_be_mistaken_for_unconfigured_bindings(value):
    data = agent_data()
    data["nodes"][0]["data"]["node"]["template"]["compaction_binding"]["value"] = value
    before = deepcopy(data)
    with pytest.raises(TypeError):
        flow_runtime_bindings(data)
    with pytest.raises(TypeError, match="JSON text"):
        compose(data, binding_for(compaction_baseline()["data"]))
    assert data == before


@pytest.mark.parametrize(
    ("outer_field", "inner_field"),
    [
        ("compaction", "context_strategy"),
        ("context_strategy", "compaction"),
        ("compaction", "hooks"),
        ("hooks", "compaction"),
        ("tool_policy", "compaction"),
        ("compaction", "tool_policy"),
        ("tool_policy", "context_strategy"),
        ("context_strategy", "tool_policy"),
        ("tool_policy", "hooks"),
        ("hooks", "tool_policy"),
    ],
)
def test_mixed_import_remaps_children_before_parent_revisions(outer_field, inner_field):
    from lfx.components.models_and_agents.agent import AgentComponent

    baselines = {
        "compaction": compaction_baseline,
        "context_strategy": context_baseline,
        "hooks": hook_baseline,
        "tool_policy": permission_baseline,
    }
    composers = {
        "compaction": compose_compaction,
        "context_strategy": compose_context,
        "hooks": compose_hooks,
        "tool_policy": compose_permission,
    }

    def bind(data, field, target, flow_id):
        output = binding_outputs(field, target)[0]
        value = {
            "flow_id": flow_id,
            "revision": flow_revision(target),
            "node_id": output["node_id"],
            "output_name": output["output_name"],
        }
        if field == "hooks":
            value = [{**value, "on_event": "before_llm_call"}]
        parsed = ProjectFlowBindings.model_validate({field: value})
        return composers[field](
            data,
            project_id="project",
            agent_id="agent",
            **{("bindings" if field == "hooks" else "binding"): getattr(parsed, field)},
        )

    leaf = baselines[inner_field]()["data"]
    outer = baselines[outer_field]()["data"]
    node = AgentComponent().to_frontend_node()
    node["id"] = node["data"]["id"] = "agent"
    node["data"]["node"]["template"]["model"]["value"] = [{"name": "Test model"}]
    nested = bind({"nodes": [node], "edges": []}, inner_field, leaf, "leaf")
    outer["nodes"].extend(nested["nodes"])
    parent = bind(agent_data(), outer_field, outer, "outer")
    flows = {"parent": parent, "outer": outer, "leaf": leaf}
    remap_runtime_bindings(flows, {key: f"new-{key}" for key in flows}, "new-project")
    for data, source, target in [(parent, outer, "new-outer"), (nested, leaf, "new-leaf")]:
        field, binding = flow_runtime_bindings(data)[0]
        assert binding.flow_id == target
        assert binding.version_id is None
        validate_project_binding(field, source, binding)
        if field == "compaction":
            assert data["nodes"][0]["data"][COMPACTION_ORIGIN] == {
                "project_id": "new-project",
                "binding": binding.model_dump(),
            }

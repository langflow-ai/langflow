"""Permission bindings use the same canvas ownership and archive contracts as other slots."""

import json
from copy import deepcopy

import pytest
from lfx.projects.baselines import permission_baseline
from lfx.projects.bindings import flow_revision, reject_recursive_binding
from lfx.projects.flow_slots import ProjectFlowBindings, flow_runtime_bindings, remap_runtime_bindings
from lfx.projects.permissions import PERMISSION_ORIGIN, PermissionBinding, compose_permission, permission_outputs

from tests.unit.projects.test_compaction_bindings import agent_data as compaction_agent_data


def agent_data():
    data = compaction_agent_data()
    data["nodes"][0]["data"]["node"]["template"]["permission_binding"] = {"value": "", "override_skip": True}
    return data


def binding_for():
    data = permission_baseline()["data"]
    output = permission_outputs(data)[0]
    return PermissionBinding(
        flow_id="source", revision=flow_revision(data), node_id=output["node_id"], output_name=output["output_name"]
    )


def compose(data, binding):
    return compose_permission(data, project_id="project", agent_id="agent", binding=binding)


def test_permission_reconciles_and_clears_only_owned_values():
    original = agent_data()
    binding = binding_for()
    configured = compose(original, binding)
    assert compose(configured, binding) == configured
    assert original == agent_data()
    assert compose(configured, None) == original
    manual = deepcopy(configured)
    manual["nodes"][0]["data"].pop(PERMISSION_ORIGIN)
    assert compose(manual, None) == manual


@pytest.mark.parametrize("defect", ["manual", "connected", "foreign", "old_agent", False, 0, [], {}])
def test_permission_canvas_conflicts_do_not_mutate_data(defect):
    binding = binding_for()
    data = compose(agent_data(), binding)
    node = data["nodes"][0]["data"]
    if defect == "old_agent":
        node["node"]["template"].pop("permission_binding")
    elif defect == "foreign":
        node[PERMISSION_ORIGIN]["project_id"] = "other"
    elif defect == "connected":
        data["edges"] = [{"target": "agent", "data": {"targetHandle": {"fieldName": "permission_binding"}}}]
    else:
        node["node"]["template"]["permission_binding"]["value"] = '{"manual":true}' if defect == "manual" else defect
    before = deepcopy(data)
    with pytest.raises((ValueError, TypeError), match="canvas"):
        compose(data, binding)
    assert data == before


def test_permission_participates_in_reference_validation():
    binding = binding_for()
    data = compose(agent_data(), binding)
    assert flow_runtime_bindings(data) == [("tool_policy", binding)]
    with pytest.raises(ValueError, match="recursive"):
        reject_recursive_binding([{"id": "source", "name": "source", "data": data}], "source", "other")
    with pytest.raises(ValueError, match="recursive"):
        remap_runtime_bindings({"source": data}, {"source": "new"}, "project")
    with pytest.raises(ValueError, match="archive"):
        remap_runtime_bindings({"agent": data}, {"agent": "new"}, "project")
    with pytest.raises(ValueError, match="tool_policy"):
        ProjectFlowBindings.model_validate({"tool_policy": [binding.model_dump()]})


def test_empty_permission_values_are_read_without_executing_code():
    data = agent_data()
    template = data["nodes"][0]["data"]["node"]["template"]
    template["code"] = {"value": "raise RuntimeError('not executed')"}
    for value in ["", " ", "null", "{}"]:
        template["permission_binding"]["value"] = value
        assert flow_runtime_bindings(data) == []
    template["permission_binding"]["value"] = json.dumps({"flow_id": "incomplete"})
    with pytest.raises(ValueError, match="tool_policy"):
        flow_runtime_bindings(data)

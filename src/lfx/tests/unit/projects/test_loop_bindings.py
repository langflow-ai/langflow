"""The AgenticLoop binding uses the same canvas ownership and archive contracts as other slots."""

import json
from copy import deepcopy

import pytest
from lfx.projects.bindings import FlowBinding, reject_recursive_binding
from lfx.projects.builtin_slots import AGENTIC_LOOP
from lfx.projects.flow_slots import ProjectFlowBindings, flow_runtime_bindings, remap_runtime_bindings

from tests.unit.projects.test_compaction_bindings import agent_data as compaction_agent_data

BINDING = FlowBinding(flow_id="source", node_id="WhileLoop-wl001", output_name="last_message", revision="r" * 8)


def agent_data():
    data = compaction_agent_data()
    data["nodes"][0]["data"]["node"]["template"]["loop_binding"] = {"value": "", "override_skip": True}
    return data


def compose(data, binding):
    return AGENTIC_LOOP.compose_binding(data, project_id="project", agent_id="agent", binding=binding)


def test_compose_writes_the_hidden_loop_input_and_clears_only_owned_values():
    original = agent_data()
    configured = compose(original, BINDING)

    node = configured["nodes"][0]["data"]
    assert json.loads(node["node"]["template"]["loop_binding"]["value"])["output_name"] == "last_message"
    assert node[AGENTIC_LOOP.origin_key]["project_id"] == "project"
    assert compose(configured, BINDING) == configured
    assert original == agent_data()
    assert compose(configured, None) == original
    manual = deepcopy(configured)
    manual["nodes"][0]["data"].pop(AGENTIC_LOOP.origin_key)
    assert compose(manual, None) == manual


def test_compose_refuses_a_canvas_edit():
    data = compose(agent_data(), BINDING)
    data["nodes"][0]["data"]["node"]["template"]["loop_binding"]["value"] = '{"manual":true}'
    before = deepcopy(data)

    with pytest.raises(ValueError, match="canvas"):
        compose(data, BINDING)

    assert data == before


def test_the_loop_binding_is_a_project_field_and_takes_part_in_reference_checks():
    data = compose(agent_data(), BINDING)

    assert ProjectFlowBindings.model_validate({"agentic_loop": BINDING.model_dump()}).entries() == [
        ("agentic_loop", BINDING)
    ]
    assert flow_runtime_bindings(data) == [("agentic_loop", BINDING)]
    with pytest.raises(ValueError, match="recursive"):
        reject_recursive_binding([{"id": "source", "name": "source", "data": data}], "source", "other")
    with pytest.raises(ValueError, match="archive"):
        remap_runtime_bindings({"agent": data}, {"agent": "new"}, "project")

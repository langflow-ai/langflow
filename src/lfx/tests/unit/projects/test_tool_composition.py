"""Project composition is usable and preserves canvas data without the API layer."""

from copy import deepcopy

import pytest
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.components.models_and_agents.agent import AgentComponent
from lfx.graph.flow_builder import add_connection
from lfx.projects import apply_project_config, get_project_type
from lfx.projects.tools import TOOL_ORIGIN, compose_tools, prepare_tool_template


def tool_flow():
    source = ChatInput().to_frontend_node()
    source["data"]["node"]["field_order"] = [field.name for field in ChatInput.inputs]
    output = ChatOutput().to_frontend_node()
    data = {"nodes": [source, output], "edges": []}
    add_connection({"data": data}, source["id"], "message", output["id"], "input_value")
    return {"id": "research-tool", "name": "Research tool", "data": data}


def test_generated_tools_preserve_canvas_edits_and_remove_only_owned_nodes():
    agent = AgentComponent().to_frontend_node()
    manual = ChatInput().to_frontend_node()
    original = {"nodes": [agent, manual], "edges": []}
    before = deepcopy(original)
    tool = tool_flow()
    composed = compose_tools(original, project_id="project", agent_id=agent["id"], targets=[tool])
    assert original == before
    generated = next(node for node in composed["nodes"] if TOOL_ORIGIN in node["data"])
    assert generated["data"]["node"]["add_tool_output"] is True
    assert composed["edges"][0]["target"] == agent["id"]
    generated["position"] = {"x": 987, "y": 654}
    generated["data"]["node"]["description"] = "Canvas customization"
    assert compose_tools(composed, project_id="project", agent_id=agent["id"], targets=[tool]) == composed
    assert compose_tools(composed, project_id="project", agent_id=agent["id"], targets=[]) == original


def test_tool_template_exposes_real_input_and_does_not_mutate_its_source():
    target = tool_flow()
    before = deepcopy(target)
    template = prepare_tool_template(target)
    assert any(field.get("tool_mode") for field in template["template"].values() if isinstance(field, dict))
    assert template["template"]["flow_id_selected"]["value"] == target["id"]
    assert target == before


def test_a_flow_without_callable_inputs_is_rejected():
    target = tool_flow()
    target["data"]["nodes"] = [ChatOutput().to_frontend_node()]
    target["data"]["edges"] = []
    with pytest.raises(ValueError, match="exposed input"):
        prepare_tool_template(target)


def test_canvas_override_keeps_the_last_applied_baseline():
    agent = AgentComponent().to_frontend_node()
    data = {"nodes": [agent], "edges": []}
    project_type = get_project_type("agent-harness")
    first = apply_project_config(data, project_type, {"system_prompt": "Form instructions"})
    first.data["nodes"][0]["data"]["node"]["template"]["system_prompt"]["value"] = "Canvas instructions"
    second = apply_project_config(
        first.data, project_type, {"system_prompt": "Updated form"}, previous_values=first.applied_values
    )
    assert second.inputs_written == 0
    assert second.inputs_skipped == 1
    assert second.data == first.data
    assert second.applied_values == first.applied_values
    second.data["nodes"][0]["data"]["node"]["template"]["system_prompt"]["value"] = "Form instructions"
    third = apply_project_config(
        second.data, project_type, {"system_prompt": "Updated form"}, previous_values=second.applied_values
    )
    assert third.inputs_written == 1
    assert third.data["nodes"][0]["data"]["node"]["template"]["system_prompt"]["value"] == "Updated form"

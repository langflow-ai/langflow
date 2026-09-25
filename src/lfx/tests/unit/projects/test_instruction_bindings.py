"""Instruction contracts and canvas composition work without the Langflow application."""

from copy import deepcopy

import pytest
from lfx.components.input_output.text_output import TextOutputComponent
from lfx.components.models_and_agents.prompt import PromptComponent
from lfx.graph.flow_builder import add_connection
from lfx.projects.bindings import (
    BINDING_ORIGIN,
    FlowBinding,
    compose_instructions,
    flow_revision,
    instruction_outputs,
    reject_recursive_binding,
    validate_instruction_result,
)
from lfx.schema.message import Message


def source_data():
    component = PromptComponent(template="Cite primary sources.")
    node = component.to_frontend_node()
    node["data"]["node"]["template"]["template"]["required"] = True
    node["id"] = node["data"]["id"] = "instructions"
    return {"nodes": [node], "edges": []}


def agent_data():
    # Only the connection contract is needed; importing Agent would load optional providers.
    return {
        "nodes": [
            {
                "id": "agent",
                "data": {
                    "type": "Agent",
                    "node": {
                        "template": {
                            "system_prompt": {"input_types": ["Message"], "type": "str", "value": "Form value"}
                        },
                        "outputs": [],
                    },
                },
                "position": {"x": 500, "y": 500},
            }
        ],
        "edges": [],
    }


def compose(data, source, binding=None):
    return compose_instructions(
        data, project_id="project", agent_id="agent", target={"name": "Instructions", "data": source}, binding=binding
    )


def binding_for(source):
    return FlowBinding(flow_id="source", node_id="instructions", output_name="prompt", revision=flow_revision(source))


def test_declared_terminal_is_discovered_without_evaluating_stored_code():
    source = source_data()
    source["nodes"][0]["data"]["node"]["template"]["code"]["value"] = "raise RuntimeError('must not execute')"
    assert instruction_outputs(source) == [
        {
            "node_id": "instructions",
            "output_name": "prompt",
            "display_name": "Prompt Template · Prompt",
        }
    ]


def test_prompt_template_is_discovered_and_composed_without_an_output_adapter():
    node = PromptComponent(template="Cite primary sources.").to_frontend_node()
    source = {"nodes": [node], "edges": []}
    before = deepcopy(source)
    choices = instruction_outputs(source)
    assert len(choices) == 1
    assert choices[0]["output_name"] == "prompt"
    binding = FlowBinding(
        flow_id="source", revision=flow_revision(source), **{key: choices[0][key] for key in ("node_id", "output_name")}
    )
    data = compose(agent_data(), source, binding)
    reference = next(node for node in data["nodes"] if BINDING_ORIGIN in node["data"])
    assert reference["data"]["node"]["outputs"][0]["types"] == ["Message"]
    assert reference["data"]["node"]["outputs"][0]["name"] == f"{node['id']}~prompt"
    assert source == before


def test_connected_prompt_is_not_offered_instead_of_its_terminal():
    source = source_data()
    node = TextOutputComponent().to_frontend_node()
    source["nodes"].append(node)
    add_connection({"data": source}, "instructions", "prompt", node["id"], "input_value")
    assert [choice["node_id"] for choice in instruction_outputs(source)] == [node["id"]]


def test_message_instruction_result_keeps_its_type_and_metadata():
    message = Message(text="Cite primary sources.", session_id="test-session")
    assert validate_instruction_result(message) is message


@pytest.mark.parametrize("value", [Message(text=""), Message(text="  "), {"text": "looks valid"}, ["text"]])
def test_instruction_result_rejects_empty_messages_and_display_values(value):
    with pytest.raises(ValueError, match="non-empty text"):
        validate_instruction_result(value)


def test_normal_component_catalog_exposes_the_terminal():
    from lfx.interface.components import _read_component_index

    index = _read_component_index()
    assert index is not None
    catalog = dict(index["entries"])
    node = deepcopy(catalog["models_and_agents"]["Prompt Template"])
    node["template"]["template"]["value"] = "Use primary sources."
    data = {
        "nodes": [{"id": "prompt", "data": {"id": "prompt", "type": "Prompt Template", "node": node}}],
        "edges": [],
    }
    assert instruction_outputs(data)[0]["output_name"] == "prompt"


def test_ambiguous_outputs_remain_explicit_choices():
    source = source_data()
    second = deepcopy(source["nodes"][0])
    second["id"] = second["data"]["id"] = "other"
    source["nodes"].append(second)
    assert {choice["node_id"] for choice in instruction_outputs(source)} == {"instructions", "other"}


def test_required_inputs_must_be_configured():
    source = source_data()
    source["nodes"][0]["data"]["node"]["template"]["template"]["value"] = ""
    with pytest.raises(ValueError, match="Configure Prompt Template: Template"):
        instruction_outputs(source)


def test_layout_changes_do_not_invalidate_the_reviewed_definition():
    source = source_data()
    revision = flow_revision(source)
    source["nodes"][0].update(position={"x": 42, "y": 87}, selected=True)
    assert flow_revision(source) == revision
    source["nodes"][0]["data"]["node"]["template"]["template"]["value"] = "Other instructions"
    assert flow_revision(source) != revision


@pytest.mark.parametrize("kind", ["self", "agent", "cycle", "name"])
def test_recursive_composition_is_rejected(kind):
    def flow(flow_id, target):
        template = {"flow_id_selected": {"value": target}}
        if kind == "name":
            template = {"flow_name_selected": {"value": target}}
        return {
            "id": flow_id,
            "name": flow_id,
            "data": {"nodes": [{"data": {"type": "RunFlow", "node": {"template": template}}}]},
        }

    target = {"self": "source", "agent": "agent", "cycle": "other", "name": "other"}[kind]
    with pytest.raises(ValueError, match="recursive"):
        reject_recursive_binding([flow("source", target), flow("other", "source")], "source", "agent")


def test_composition_is_idempotent_and_preserves_user_connections():
    source = source_data()
    binding = binding_for(source)
    data = compose(agent_data(), source, binding)
    assert compose(data, source, binding) == data
    assert len(data["nodes"]) == 2
    generated = next(node for node in data["nodes"] if BINDING_ORIGIN in node["data"])
    generated["position"] = {"x": 12, "y": 23}
    updated = binding.model_copy(update={"version_id": "reviewed"})
    recomposed = compose(data, source, updated)
    assert next(node for node in recomposed["nodes"] if BINDING_ORIGIN in node["data"])["position"] == {
        "x": 12,
        "y": 23,
    }
    custom = deepcopy(data["edges"][0])
    custom["target"] = "another-component"
    data["edges"].append(custom)
    with pytest.raises(ValueError, match="custom canvas connections"):
        compose(data, source)


def test_manual_prompt_connection_is_not_replaced():
    source = source_data()
    data = agent_data()
    data["nodes"][0]["data"]["node"]["template"]["system_prompt"]["input_types"].append("Text")
    data["nodes"].append(source["nodes"][0])
    add_connection({"data": data}, "instructions", "prompt", "agent", "system_prompt")
    before = deepcopy(data)
    with pytest.raises(ValueError, match="already has a canvas connection"):
        compose(data, source, binding_for(source))
    assert data == before


def test_edited_output_connection_is_not_silently_accepted():
    source = source_data()
    binding = binding_for(source)
    data = compose(agent_data(), source, binding)
    data["edges"][0]["data"]["sourceHandle"]["name"] = "other~output"
    with pytest.raises(ValueError, match="edited on the canvas"):
        compose(data, source, binding)


@pytest.mark.parametrize("text", ["", "  "])
def test_empty_runtime_instructions_fail_explicitly(text):
    with pytest.raises(ValueError, match="non-empty text"):
        validate_instruction_result(text)

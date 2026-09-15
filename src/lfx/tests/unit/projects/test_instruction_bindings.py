"""Instruction contracts and canvas composition work without the Langflow application."""

from copy import deepcopy

import pytest
from lfx.components.models_and_agents.system_prompt_builder import SystemPromptBuilderComponent
from lfx.graph.flow_builder import add_connection
from lfx.projects.bindings import (
    BINDING_ORIGIN,
    BoundFlowDependency,
    FlowBinding,
    compose_instructions,
    flow_revision,
    instruction_outputs,
    reject_recursive_binding,
)


@pytest.mark.parametrize("mode", ["python", "json"])
def test_flat_bindings_keep_their_archived_shape_while_nested_versions_round_trip(mode):
    original = {
        "flow_id": "source",
        "node_id": "instructions",
        "output_name": "instructions",
        "revision": "reviewed",
        "version_id": "source-version",
    }
    binding = FlowBinding.model_validate(original)
    assert binding.model_dump(mode=mode) == original
    binding.dependencies = [
        BoundFlowDependency(flow_id="child", name="Rules", revision="child-revision", version_id="child-version")
    ]
    restored = FlowBinding.model_validate_json(binding.model_dump_json())
    assert restored == binding
    assert restored.model_dump(mode=mode)["dependencies"][0]["version_id"] == "child-version"


def source_data():
    component = SystemPromptBuilderComponent(input_value="Cite primary sources.")
    node = component.to_frontend_node()
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
    return FlowBinding(
        flow_id="source", node_id="instructions", output_name="instructions", revision=flow_revision(source)
    )


def test_declared_terminal_is_discovered_without_evaluating_stored_code():
    source = source_data()
    source["nodes"][0]["data"]["node"]["template"]["code"]["value"] = "raise RuntimeError('must not execute')"
    assert instruction_outputs(source) == [
        {
            "node_id": "instructions",
            "output_name": "instructions",
            "display_name": "System Prompt Builder · Instructions",
        }
    ]


def test_normal_component_catalog_exposes_the_terminal():
    from lfx.interface.components import _read_component_index

    index = _read_component_index()
    assert index is not None
    catalog = dict(index["entries"])
    node = deepcopy(catalog["models_and_agents"]["SystemPromptBuilder"])
    node["template"]["input_value"]["value"] = "Use primary sources."
    data = {
        "nodes": [{"id": "builder", "data": {"id": "builder", "type": "SystemPromptBuilder", "node": node}}],
        "edges": [],
    }
    assert instruction_outputs(data)[0]["output_name"] == "instructions"


def test_ambiguous_outputs_remain_explicit_choices():
    source = source_data()
    second = deepcopy(source["nodes"][0])
    second["id"] = second["data"]["id"] = "other"
    source["nodes"].append(second)
    assert {choice["node_id"] for choice in instruction_outputs(source)} == {"instructions", "other"}


def test_required_inputs_must_be_configured():
    source = source_data()
    source["nodes"][0]["data"]["node"]["template"]["input_value"]["value"] = ""
    with pytest.raises(ValueError, match="Configure System Prompt Builder: Instructions"):
        instruction_outputs(source)


def test_layout_changes_do_not_invalidate_the_reviewed_definition():
    source = source_data()
    revision = flow_revision(source)
    source["nodes"][0].update(position={"x": 42, "y": 87}, selected=True)
    assert flow_revision(source) == revision
    source["nodes"][0]["data"]["node"]["template"]["input_value"]["value"] = "Other instructions"
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
    add_connection({"data": data}, "instructions", "instructions", "agent", "system_prompt")
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
    component = SystemPromptBuilderComponent(input_value=text)
    with pytest.raises(ValueError, match="non-empty text"):
        component.build_instructions()

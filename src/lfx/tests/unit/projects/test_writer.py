"""The form writes through to the flow.

``project_config`` records what a person picked; it is not what runs. These tests hold the rule
that makes the design work: a field with a write-through target really does land on the matching
component in the flow, and a field without one changes nothing.

The Agent node here is the real serialised component, not a hand-made payload, so the template
shape being written into is the shape a flow actually holds.
"""

import pytest
from lfx.components.models_and_agents.agent import AgentComponent
from lfx.inputs.inputs import StrInput
from lfx.projects import apply_project_config, get_project_type
from lfx.projects.schema import FieldTarget, ProjectType, ProjectTypeField


def agent_node(node_id: str = "Agent-1") -> dict:
    """A flow node holding the real Agent component."""
    frontend = AgentComponent().to_frontend_node()
    return {"id": node_id, "data": frontend.get("data", frontend)}


def flow_with(*nodes: dict) -> dict:
    return {"nodes": list(nodes), "edges": []}


def template_of(data: dict, index: int = 0) -> dict:
    return data["nodes"][index]["data"]["node"]["template"]


@pytest.fixture
def harness():
    return get_project_type("agent-harness")


class TestWritingThrough:
    def test_a_targeted_field_lands_on_the_component(self, harness):
        flow = flow_with(agent_node())

        result = apply_project_config(flow, harness, {"system_prompt": "Be terse"})

        assert result.inputs_written == 1
        assert template_of(result.data)["system_prompt"]["value"] == "Be terse"

    def test_every_targeted_field_the_config_holds_is_written(self, harness):
        flow = flow_with(agent_node())

        result = apply_project_config(flow, harness, {"system_prompt": "Be terse", "n_messages": 7})

        written = template_of(result.data)
        assert written["system_prompt"]["value"] == "Be terse"
        assert written["n_messages"]["value"] == 7

    def test_every_matching_component_in_the_flow_is_written(self, harness):
        """A harness project's config describes its agent, wherever that agent appears."""
        flow = flow_with(agent_node("Agent-1"), agent_node("Agent-2"))

        result = apply_project_config(flow, harness, {"system_prompt": "Be terse"})

        assert result.inputs_written == 2
        assert template_of(result.data, 0)["system_prompt"]["value"] == "Be terse"
        assert template_of(result.data, 1)["system_prompt"]["value"] == "Be terse"

    def test_the_flow_it_was_given_is_left_alone(self, harness):
        """Callers hold the stored flow, so the write has to hand back a copy."""
        flow = flow_with(agent_node())
        before = template_of(flow)["system_prompt"]["value"]

        apply_project_config(flow, harness, {"system_prompt": "Be terse"})

        assert template_of(flow)["system_prompt"]["value"] == before


class TestWhatIsNotWritten:
    def test_a_field_with_no_target_is_recorded_and_nothing_more(self):
        """Recording a choice and running it are different things; only a target crosses over."""
        project_type = ProjectType(
            name="test-untargeted",
            display_name="Untargeted",
            icon="Box",
            fields=(ProjectTypeField(name="note", input=StrInput(name="note", display_name="Note")),),
        )
        flow = flow_with(agent_node())

        result = apply_project_config(flow, project_type, {"note": "anything"})

        assert result.inputs_written == 0
        assert result.changed is False

    def test_a_component_the_type_does_not_target_is_untouched(self, harness):
        other = agent_node("Other-1")
        other["data"]["type"] = "SomethingElse"
        flow = flow_with(other)

        result = apply_project_config(flow, harness, {"system_prompt": "Be terse"})

        assert result.inputs_written == 0
        assert template_of(result.data)["system_prompt"]["value"] != "Be terse"

    def test_an_input_the_component_does_not_have_is_not_invented(self):
        """Writing a key the component never declared would produce a template it cannot read."""
        project_type = ProjectType(
            name="test-absent-input",
            display_name="Absent",
            icon="Box",
            fields=(
                ProjectTypeField(
                    name="nope",
                    writes_to=FieldTarget("Agent", "not_an_input"),
                    input=StrInput(name="nope", display_name="Nope"),
                ),
            ),
        )
        flow = flow_with(agent_node())

        result = apply_project_config(flow, project_type, {"nope": "x"})

        assert result.inputs_written == 0
        assert "not_an_input" not in template_of(result.data)

    def test_a_field_the_config_never_set_is_skipped(self, harness):
        """A config saved before a field existed must not blank that field out."""
        flow = flow_with(agent_node())
        before = template_of(flow)["n_messages"]["value"]

        result = apply_project_config(flow, harness, {"system_prompt": "Be terse"})

        assert template_of(result.data)["n_messages"]["value"] == before

    def test_a_value_the_flow_already_holds_is_not_rewritten(self, harness):
        """Nothing to save means nothing to save, so a no-op does not touch the flow."""
        flow = flow_with(agent_node())
        current = template_of(flow)["system_prompt"]["value"]

        result = apply_project_config(flow, harness, {"system_prompt": current})

        assert result.inputs_written == 0
        assert result.changed is False


class TestFlowsItCannotWrite:
    @pytest.mark.parametrize(
        "flow",
        [
            pytest.param(None, id="no data"),
            pytest.param({}, id="no nodes"),
            pytest.param({"nodes": "not a list"}, id="nodes is not a list"),
            pytest.param({"nodes": [{"id": "x"}]}, id="node has no data"),
            pytest.param({"nodes": [{"id": "x", "data": {"type": "Agent"}}]}, id="node has no template"),
            pytest.param({"nodes": ["not a node"]}, id="node is not a mapping"),
        ],
    )
    def test_a_flow_it_cannot_read_is_left_alone_rather_than_failing(self, flow, harness):
        """One odd flow in a project must not fail the save for the rest."""
        result = apply_project_config(flow, harness, {"system_prompt": "Be terse"})

        assert result.inputs_written == 0

    def test_an_empty_config_writes_nothing(self, harness):
        flow = flow_with(agent_node())

        assert apply_project_config(flow, harness, {}).inputs_written == 0
        assert apply_project_config(flow, harness, None).inputs_written == 0


class TestAgainstTheRealHarnessType:
    def test_the_harness_only_targets_inputs_it_can_actually_set(self, harness):
        """A target has to be a value the component can consume, not just a key that exists."""
        flow = flow_with(agent_node())
        config = {field.name: "written" for field in harness.fields if field.writes_to is not None}

        result = apply_project_config(flow, harness, config)

        written = template_of(result.data)
        for field in harness.fields:
            if field.writes_to is None:
                continue
            assert written[field.writes_to.input_name]["value"] == "written"

    def test_the_flow_picker_does_not_write_through(self, harness):
        """The Agent's tools are objects built from the graph; flow ids there would break a run."""
        flow = flow_with(agent_node())

        result = apply_project_config(flow, harness, {"tools": ["a-flow-id"]})

        assert result.inputs_written == 0
        assert template_of(result.data)["tools"]["value"] != ["a-flow-id"]

from typing import Any

import pytest
from langflow.components.crewai import CrewAIAgentComponent, SequentialTaskComponent
from langflow.components.custom_component import CustomComponent
from langflow.components.input_output import ChatInput, ChatOutput
from langflow.custom.utils import update_component_build_config
from langflow.schema import dotdict
from langflow.template import Output
from typing_extensions import override

crewai_available = False
try:
    import crewai  # noqa: F401

    crewai_available = True
except ImportError:
    pass


def test_set_invalid_output():
    chatinput = ChatInput()
    chatoutput = ChatOutput()
    with pytest.raises(ValueError, match="Method build_config is not a valid output of ChatInput"):
        chatoutput.set(input_value=chatinput.build_config)


@pytest.mark.skipif(not crewai_available, reason="CrewAI is not installed")
def test_set_component():
    crewai_agent = CrewAIAgentComponent()
    task = SequentialTaskComponent()
    task.set(agent=crewai_agent)
    assert task._edges[0]["source"] == crewai_agent._id
    assert crewai_agent in task._components


def _output_required_inputs_are_in_inputs(output: Output, inputs: list[str]):
    return all(input_type in inputs for input_type in output.required_inputs)


def _assert_all_outputs_have_different_required_inputs(outputs: list[Output]):
    required_inputs = [tuple(output.required_inputs) for output in outputs]
    assert len(required_inputs) == len(set(required_inputs)), "All outputs must have different required inputs"
    return True


# These don't make a ton of sense to test because the inputs are dynamic
# def test_set_required_inputs():
#     chatinput = ChatInput()

#     assert all(_output_required_inputs_are_in_inputs(output, chatinput._inputs) for output in chatinput.outputs)
#     assert _assert_all_outputs_have_different_required_inputs(chatinput.outputs)


# def test_set_required_inputs_various_components():
#     chatinput = ChatInput()
#     chatoutput = ChatOutput()
#     task = SequentialTaskComponent()
#     agent = AgentComponent()
#     openai_component = OpenAIModelComponent()

#     assert all(_output_required_inputs_are_in_inputs(output, chatinput._inputs) for output in chatinput.outputs)
#     assert all(_output_required_inputs_are_in_inputs(output, chatoutput._inputs) for output in chatoutput.outputs)
#     assert all(_output_required_inputs_are_in_inputs(output, task._inputs) for output in task.outputs)
#     assert all(_output_required_inputs_are_in_inputs(output, agent._inputs) for output in agent.outputs)
#     assert all(
#         _output_required_inputs_are_in_inputs(output, openai_component._inputs) for output in openai_component.outputs
#     )

#     assert _assert_all_outputs_have_different_required_inputs(chatinput.outputs)
#     assert _assert_all_outputs_have_different_required_inputs(chatoutput.outputs)
#     assert _assert_all_outputs_have_different_required_inputs(task.outputs)
#     assert _assert_all_outputs_have_different_required_inputs(agent.outputs)


async def test_update_component_build_config_sync():
    class TestComponent(CustomComponent):
        @override
        def update_build_config(
            self,
            build_config: dotdict,
            field_value: Any,
            field_name: str | None = None,
        ):
            build_config["foo"] = "bar"
            return build_config

    component = TestComponent()
    build_config = dotdict()
    build_config = await update_component_build_config(component, build_config, "", "")
    assert build_config["foo"] == "bar"


async def test_update_component_build_config_async():
    class TestComponent(CustomComponent):
        @override
        async def update_build_config(
            self,
            build_config: dotdict,
            field_value: Any,
            field_name: str | None = None,
        ):
            build_config["foo"] = "bar"
            return build_config

    component = TestComponent()
    build_config = dotdict()
    build_config = await update_component_build_config(component, build_config, "", "")
    assert build_config["foo"] == "bar"

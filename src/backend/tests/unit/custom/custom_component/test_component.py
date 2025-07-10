from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from langflow.components.crewai import CrewAIAgentComponent, SequentialTaskComponent
from langflow.components.custom_component import CustomComponent
from langflow.components.input_output import ChatInput, ChatOutput
from langflow.custom.custom_component.component import Component
from langflow.custom.utils import update_component_build_config
from langflow.schema import dotdict
from langflow.schema.message import Message
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


@pytest.mark.xfail(reason="CrewAI is not outdated")
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


@pytest.mark.asyncio
async def test_send_message_without_database(monkeypatch):
    component = Component()
    # Mock _is_database_available to return False
    monkeypatch.setattr(component, "_is_database_available", lambda: False)
    # Mock event manager and its on_message method
    event_manager = MagicMock()
    component._event_manager = event_manager
    # Mock _store_message and _update_stored_message to ensure they are not called
    component._store_message = AsyncMock()
    component._update_stored_message = AsyncMock()
    # Create a dummy message
    message = Message(text="Hello", session_id="session", flow_id=None)
    # Call send_message
    result = await component.send_message(message)
    # Assert the returned message is the same as input
    assert result == message
    # Assert _store_message and _update_stored_message were not called
    component._store_message.assert_not_called()
    component._update_stored_message.assert_not_called()
    # Assert event manager's on_message was called
    assert event_manager.on_message.called

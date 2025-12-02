from typing import Any
from unittest.mock import MagicMock

import pytest
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.custom.custom_component.component import Component
from lfx.custom.custom_component.custom_component import CustomComponent
from lfx.custom.utils import update_component_build_config
from lfx.schema.dotdict import dotdict
from lfx.schema.message import Message
from lfx.template import Output

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
    from lfx.components.crewai import CrewAIAgentComponent, SequentialTaskComponent

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


@pytest.mark.asyncio
async def test_update_component_build_config_sync():
    class TestComponent(CustomComponent):
        def update_build_config(
            self,
            build_config: dotdict,
            field_value: Any,  # noqa: ARG002
            field_name: str | None = None,  # noqa: ARG002
        ):
            build_config["foo"] = "bar"
            return build_config

    component = TestComponent()
    build_config = dotdict()
    build_config = await update_component_build_config(component, build_config, "", "")
    assert build_config["foo"] == "bar"


@pytest.mark.asyncio
async def test_update_component_build_config_async():
    class TestComponent(CustomComponent):
        async def update_build_config(
            self,
            build_config: dotdict,
            field_value: Any,  # noqa: ARG002
            field_name: str | None = None,  # noqa: ARG002
        ):
            build_config["foo"] = "bar"
            return build_config

    component = TestComponent()
    build_config = dotdict()
    build_config = await update_component_build_config(component, build_config, "", "")
    assert build_config["foo"] == "bar"


@pytest.mark.asyncio
async def test_send_message_without_database():
    from unittest.mock import AsyncMock

    component = Component()
    event_manager = MagicMock()
    component._event_manager = event_manager
    message = Message(text="Hello", session_id="session", flow_id=None, sender="User", sender_name="Test")

    # Mock _store_message to avoid database interaction
    async def mock_store_message(msg):
        # Simulate what _store_message does: add an ID and return the message
        msg.data["id"] = "test-message-id"
        return msg

    component._store_message = AsyncMock(side_effect=mock_store_message)

    result = await component.send_message(message)
    assert isinstance(result, Message)
    assert result.text == "Hello"
    assert result.sender == "User"
    assert result.sender_name == "Test"
    # Verify the message was stored (mock was called)
    component._store_message.assert_called_once()
    # The focus is on testing the message handling logic, not the database persistence layer
    assert event_manager.on_message.called


@pytest.mark.usefixtures("use_noop_session")
@pytest.mark.asyncio
async def test_agent_component_send_message_events(monkeypatch):  # noqa: ARG001
    try:
        import langchain  # noqa: F401
    except ImportError:
        pytest.skip("Langchain is not installed")

    from lfx.components.models_and_agents.agent import AgentComponent

    event_manager = MagicMock()
    agent = AgentComponent(
        agent_llm="OpenAI",
        input_value="Hello",
        system_prompt="You are a helpful assistant.",
        tools=[],
        _session_id="test-session",
    )
    agent._event_manager = event_manager
    message = Message(text="Hello", session_id="test-session", flow_id=None, sender="User", sender_name="Test")

    result = await agent.send_message(message)
    assert isinstance(result, Message)
    assert result.text == "Hello"
    assert result.sender == "User"
    assert result.sender_name == "Test"
    # The focus is on testing the message handling logic, not the database persistence layer
    assert event_manager.on_message.called


class TestComponentOutputProperty:
    """Tests for the .output property and passing components directly to .set()."""

    def test_output_returns_bound_method(self):
        """Test that .output returns the bound method for the default output."""
        chat_input = ChatInput()

        # .output should return the bound method, not the Output object
        assert callable(chat_input.output)
        assert hasattr(chat_input.output, "__self__")
        assert chat_input.output.__self__ is chat_input

    def test_output_returns_first_output_method(self):
        """Test that .output returns the first output's method by default."""
        chat_input = ChatInput()

        # Get the first output's method name
        first_output = next(iter(chat_input._outputs_map.values()))
        expected_method = getattr(chat_input, first_output.method)

        # .output should return the same method
        assert chat_input.output.__name__ == expected_method.__name__

    def test_output_respects_selected_output(self):
        """Test that .output uses selected_output when set."""
        chat_input = ChatInput()

        # ChatInput has multiple outputs, set selected_output to a different one
        outputs = list(chat_input._outputs_map.keys())
        if len(outputs) > 1:
            # Select a different output than the default
            chat_input.selected_output = outputs[1]
            selected_output_obj = chat_input._outputs_map[outputs[1]]

            assert chat_input.output.__name__ == selected_output_obj.method

    def test_output_raises_error_when_no_outputs(self):
        """Test that .output raises ValueError when component has no outputs."""

        class NoOutputComponent(Component):
            outputs = []

        component = NoOutputComponent()
        with pytest.raises(ValueError, match="has no outputs defined"):
            _ = component.output

    def test_set_with_component_uses_output(self):
        """Test that passing a Component to .set() uses its .output property."""
        chat_input = ChatInput()
        chat_output = ChatOutput()

        # Pass component directly instead of component.output
        chat_output.set(input_value=chat_input)

        # Should create an edge
        assert len(chat_output._edges) == 1
        assert chat_output._edges[0]["source"] == chat_input._id
        assert chat_input in chat_output._components

    def test_set_with_component_equivalent_to_output(self):
        """Test that .set(comp) creates the same edge as .set(comp.output)."""
        chat_input1 = ChatInput()
        chat_output1 = ChatOutput()
        chat_output1.set(input_value=chat_input1)

        chat_input2 = ChatInput()
        chat_output2 = ChatOutput()
        chat_output2.set(input_value=chat_input2.output)

        # Both should create edges with the same structure
        edge1 = chat_output1._edges[0]
        edge2 = chat_output2._edges[0]

        # Source handle should reference the same output
        assert edge1["data"]["sourceHandle"]["name"] == edge2["data"]["sourceHandle"]["name"]
        assert edge1["data"]["targetHandle"]["fieldName"] == edge2["data"]["targetHandle"]["fieldName"]

    def test_set_with_explicit_output_method(self):
        """Test that passing an explicit output method still works."""
        chat_input = ChatInput()
        chat_output = ChatOutput()

        # Explicit method reference should still work
        chat_output.set(input_value=chat_input.message_response)

        assert len(chat_output._edges) == 1
        assert chat_output._edges[0]["source"] == chat_input._id

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lfx.components.input_output import ChatInput, ChatOutput
from lfx.custom.custom_component.component import Component
from lfx.custom.custom_component.custom_component import CustomComponent
from lfx.custom.utils import update_component_build_config
from lfx.schema import dotdict
from lfx.schema.message import Message
from lfx.services.session import NoopSession
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


@pytest.mark.usefixtures("use_noop_session")
@pytest.mark.asyncio
async def test_send_message_without_database(monkeypatch):  # noqa: ARG001
    component = Component()
    event_manager = MagicMock()
    component._event_manager = event_manager
    message = Message(text="Hello", session_id="session", flow_id=None, sender="User", sender_name="Test")
    with (
        patch.object(NoopSession, "add", new_callable=AsyncMock) as mock_add,
        patch.object(NoopSession, "commit", new_callable=AsyncMock) as mock_commit,
    ):
        result = await component.send_message(message)
        assert isinstance(result, Message)
        assert result.text == "Hello"
        assert result.sender == "User"
        assert result.sender_name == "Test"
        # Optionally, check that add/commit were called (if you want to enforce this)
        assert mock_add.called
        assert mock_commit.called
    assert event_manager.on_message.called


@pytest.mark.usefixtures("use_noop_session")
@pytest.mark.asyncio
async def test_agent_component_send_message_events(monkeypatch):  # noqa: ARG001
    from lfx.components.agents.agent import AgentComponent

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
    with (
        patch.object(NoopSession, "add", new_callable=AsyncMock) as mock_add,
        patch.object(NoopSession, "commit", new_callable=AsyncMock) as mock_commit,
    ):
        result = await agent.send_message(message)
        assert isinstance(result, Message)
        assert result.text == "Hello"
        assert result.sender == "User"
        assert result.sender_name == "Test"
        # Optionally, check that add/commit were called (if you want to enforce this)
        assert mock_add.called
        assert mock_commit.called
    assert event_manager.on_message.called

from typing import Any
from unittest.mock import MagicMock

import pytest
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.custom.custom_component.component import Component
from lfx.custom.custom_component.custom_component import CustomComponent
from lfx.custom.utils import update_component_build_config
from lfx.inputs.inputs import (
    AuthInput,
    ConnectionInput,
    ConnectionRefInput,
    FileInput,
    McpInput,
    MultilineSecretInput,
    SecretStrInput,
    StrInput,
)
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


@pytest.mark.parametrize("repr_value", ["", "Explicit preview", {"preview": "Explicit preview"}])
def test_custom_repr_tracks_status_without_overwriting_explicit_value(repr_value):
    component = Component()
    component.repr_value = repr_value
    component.status = "First output"
    first_repr = component.custom_repr()

    component.status = "Second output"
    second_repr = component.custom_repr()

    if repr_value == "":
        assert first_repr == "First output"
        assert second_repr == "Second output"
    else:
        assert first_repr == second_repr
        assert "Explicit preview" in second_repr
    assert component.repr_value == repr_value


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


@pytest.mark.asyncio
async def test_process_chunk_marks_first_event_partial_without_mutating_message():
    component = Component()
    messages: list[dict] = []
    tokens: list[dict] = []

    class EventManager:
        def on_message(self, data):
            messages.append(data)

        def on_token(self, data):
            tokens.append(data)

    component._event_manager = EventManager()
    message = Message(text="", sender="AI")
    message.properties.state = "complete"

    complete_message = await component._process_chunk("", "", "message-id", message, first_chunk=True)

    assert complete_message == ""
    assert message.properties.state == "complete"
    assert messages[0]["properties"]["state"] == "partial"
    assert tokens == [{"chunk": "", "id": "message-id"}]


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


def test_extract_data_returns_dataframe_unchanged():
    pd = pytest.importorskip("pandas")

    component = Component()
    dataframe = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})

    extracted = component.extract_data(dataframe)
    assert extracted is dataframe


def test_extract_data_returns_series_unchanged():
    pd = pytest.importorskip("pandas")

    component = Component()
    series = pd.Series([1, 2, 3], name="numbers")

    extracted = component.extract_data(series)
    assert extracted is series


def test_trace_redacts_runtime_and_metadata_secrets():
    class TraceComponent(Component):
        inputs = [
            # These two types do not opt into the predefined-input trace map,
            # so they exercise the runtime-input map exclusively.
            SecretStrInput(name="runtime_secret", display_name="Runtime Secret"),
            StrInput(name="runtime_label", display_name="Runtime Label", value="metadata-safe-label"),
            MultilineSecretInput(
                name="metadata_secret",
                display_name="Metadata Secret",
                value="metadata-secret-sentinel",  # pragma: allowlist secret
            ),
        ]

    component = TraceComponent()
    component.set_attributes(
        {
            "runtime_secret": "secret-sentinel",  # pragma: allowlist secret
            "runtime_label": "runtime-safe-label",
            "metadata_secret": "runtime-metadata-secret-sentinel",  # pragma: allowlist secret
        }
    )

    assert component.get_trace_as_inputs() == {
        "runtime_secret": "**********",
        "runtime_label": "runtime-safe-label",
        "metadata_secret": "**********",
    }
    assert component.get_trace_as_metadata() == {
        "runtime_label": "metadata-safe-label",
        "metadata_secret": "**********",
    }


def test_trace_masks_credential_field_types():
    class TraceComponent(Component):
        inputs = [
            AuthInput(name="auth", value="https://auth.example.com/?code=metadata-sentinel"),
            ConnectionInput(
                name="connection",
                value="postgresql://app:metadata-sentinel@db/app",  # pragma: allowlist secret
            ),
            McpInput(name="mcp_server", value={"name": "server", "config": {"env": {"TOKEN": "metadata-sentinel"}}}),
            # A connection reference is a non-secret handle and a file path is not a credential.
            ConnectionRefInput(name="connection_ref", provider="github", value="github/metadata"),
            FileInput(name="path", value="/data/metadata.txt"),
            StrInput(name="label", value="metadata-label"),
        ]

    component = TraceComponent()
    component.set_attributes(
        {
            "auth": "https://auth.example.com/?code=runtime-sentinel",
            "connection": "postgresql://app:runtime-sentinel@db/app",  # pragma: allowlist secret
            "mcp_server": {"name": "server", "config": {"headers": {"Authorization": "Bearer runtime-sentinel"}}},
            "connection_ref": "github/runtime",
            "path": "/data/runtime.txt",
            "label": "runtime-label",
        }
    )

    masked = {"auth": "**********", "connection": "**********", "mcp_server": "**********"}
    assert component.get_trace_as_inputs() == {
        **masked,
        "connection_ref": "github/runtime",
        "path": "/data/runtime.txt",
        "label": "runtime-label",
    }
    assert component.get_trace_as_metadata() == {
        **masked,
        "connection_ref": "github/metadata",
        "path": "/data/metadata.txt",
        "label": "metadata-label",
    }

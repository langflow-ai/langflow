import os
from typing import Any
from uuid import uuid4

import pytest
from langflow.custom import Component
from lfx.base.models.anthropic_constants import ANTHROPIC_MODELS
from lfx.base.models.model_input_constants import (
    MODEL_PROVIDERS,
)
from lfx.base.models.openai_constants import (
    OPENAI_CHAT_MODEL_NAMES,
    OPENAI_REASONING_MODEL_NAMES,
)
from lfx.components.agents import AgentComponent
from lfx.components.tools.calculator import CalculatorToolComponent

from tests.base import ComponentTestBaseWithClient, ComponentTestBaseWithoutClient
from tests.unit.mock_language_model import MockLanguageModel

# Load environment variables from .env file


class TestAgentComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return AgentComponent

    @pytest.fixture
    def file_names_mapping(self):
        return []

    async def component_setup(self, component_class: type[Any], default_kwargs: dict[str, Any]) -> Component:
        component_instance = await super().component_setup(component_class, default_kwargs)
        # Mock _should_process_output method
        component_instance._should_process_output = lambda output: False  # noqa: ARG005
        return component_instance

    @pytest.fixture
    def default_kwargs(self):
        return {
            "_type": "Agent",
            "add_current_date_tool": True,
            "agent_description": "A helpful agent",
            "agent_llm": MockLanguageModel(),
            "handle_parsing_errors": True,
            "input_value": "",
            "max_iterations": 10,
            "system_prompt": "You are a helpful assistant.",
            "tools": [],
            "verbose": True,
            "n_messages": 100,
            "format_instructions": "You are an AI that extracts structured JSON objects from unstructured text.",
            "output_schema": [],
        }

    async def test_build_config_update(self, component_class, default_kwargs):
        component = await self.component_setup(component_class, default_kwargs)
        frontend_node = component.to_frontend_node()
        build_config = frontend_node["data"]["node"]["template"]
        # Test updating build config for OpenAI
        component.set(agent_llm="OpenAI")
        updated_config = await component.update_build_config(build_config, "OpenAI", "agent_llm")
        assert "agent_llm" in updated_config
        assert updated_config["agent_llm"]["value"] == "OpenAI"
        assert isinstance(updated_config["agent_llm"]["options"], list)
        assert len(updated_config["agent_llm"]["options"]) > 0
        assert all(provider in updated_config["agent_llm"]["options"] for provider in MODEL_PROVIDERS)
        assert (
            updated_config["agent_llm"]["external_options"]["fields"]["data"]["node"]["name"] == "connect_other_models"
        )

        # Verify model_name field is populated for OpenAI

        assert "model_name" in updated_config
        model_name_dict = updated_config["model_name"]
        assert isinstance(model_name_dict["options"], list)
        assert len(model_name_dict["options"]) > 0  # OpenAI should have available models
        assert "gpt-4o" in model_name_dict["options"]

        # Test Anthropic
        component.set(agent_llm="Anthropic")
        updated_config = await component.update_build_config(build_config, "Anthropic", "agent_llm")
        assert "agent_llm" in updated_config
        assert updated_config["agent_llm"]["value"] == "Anthropic"
        assert isinstance(updated_config["agent_llm"]["options"], list)
        assert len(updated_config["agent_llm"]["options"]) > 0
        assert all(provider in updated_config["agent_llm"]["options"] for provider in MODEL_PROVIDERS)
        assert "Anthropic" in updated_config["agent_llm"]["options"]
        assert updated_config["agent_llm"]["input_types"] == []
        options = updated_config["model_name"]["options"]
        assert any("sonnet" in option.lower() for option in options), f"Options: {options}"

        # Test updating build config for Custom
        updated_config = await component.update_build_config(
            build_config, field_value="connect_other_models", field_name="agent_llm"
        )
        assert "agent_llm" in updated_config
        # NOTE: update this when external options are available as values in options.
        # assert updated_config["agent_llm"]["value"] == "connect_other_models"
        assert isinstance(updated_config["agent_llm"]["options"], list)
        assert len(updated_config["agent_llm"]["options"]) > 0
        assert all(provider in updated_config["agent_llm"]["options"] for provider in MODEL_PROVIDERS)
        assert (
            updated_config["agent_llm"]["external_options"]["fields"]["data"]["node"]["name"] == "connect_other_models"
        )
        assert updated_config["agent_llm"]["input_types"] == ["LanguageModel"]

        # Verify model_name field is cleared for Custom
        assert "model_name" not in updated_config

    async def test_agent_filters_empty_chat_history_messages(self):
        """Test that empty messages in chat history are filtered out."""
        from lfx.base.agents.utils import data_to_messages
        from lfx.schema.message import Message

        # Create messages with varying content
        empty_message = Message(text="", sender="User", sender_name="User")
        whitespace_message = Message(text="   ", sender="User", sender_name="User")
        valid_message = Message(text="Hello", sender="User", sender_name="User")

        # Convert to LC messages (should filter out empty ones)
        messages = data_to_messages([empty_message, whitespace_message, valid_message])

        # Should only have the valid message
        assert len(messages) == 1
        assert messages[0].content == "Hello"

    async def test_agent_receives_string_input_from_message_object(self, component_class, default_kwargs):
        """Test that agent extracts text string from Message object instead of passing the entire object.

        This test addresses the issue where agents were receiving:
        content='hi how are you' additional_kwargs={} response_metadata={}
        instead of just the string 'hi how are you'.
        """
        from langchain_core.messages import HumanMessage
        from lfx.schema.message import Message

        # Create a Message object with text content
        message = Message(text="hi how are you", sender="User", sender_name="User")

        # Set up the component with the Message as input
        default_kwargs["input_value"] = message
        component = await self.component_setup(component_class, default_kwargs)

        # Test the input processing logic directly
        # This is what happens inside the agent when processing input
        lc_message = None
        if isinstance(component.input_value, Message):
            lc_message = component.input_value.to_lc_message()

            # Verify it's a LangChain HumanMessage
            assert isinstance(lc_message, HumanMessage)
            assert lc_message.content == "hi how are you"

            # Now verify the extraction logic that should happen in the agent
            if hasattr(lc_message, "content"):
                if isinstance(lc_message.content, str):
                    input_dict = {"input": lc_message.content}
                    # The key assertion: input should be a string, not a Message object
                    assert isinstance(input_dict["input"], str)
                    assert input_dict["input"] == "hi how are you"
                    # Ensure it's NOT the message object representation
                    assert "additional_kwargs" not in str(input_dict["input"])
                    assert "response_metadata" not in str(input_dict["input"])
                elif isinstance(lc_message.content, list):
                    # For multimodal content, extract text parts
                    text_parts = [item.get("text", "") for item in lc_message.content if item.get("type") == "text"]
                    input_dict = {"input": " ".join(text_parts) if text_parts else ""}
                    assert isinstance(input_dict["input"], str)
                else:
                    input_dict = {"input": str(lc_message.content)}
                    assert isinstance(input_dict["input"], str)


class TestAgentComponentWithClient(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return AgentComponent

    @pytest.fixture
    def file_names_mapping(self):
        return []

    @pytest.mark.api_key_required
    @pytest.mark.no_blockbuster
    async def test_agent_component_with_calculator(self):
        # Now you can access the environment variables
        from tests.api_keys import get_openai_api_key

        api_key = get_openai_api_key()
        tools = [CalculatorToolComponent().build_tool()]  # Use the Calculator component as a tool
        input_value = "What is 2 + 2?"

        temperature = 0.1

        # Initialize the AgentComponent with mocked inputs
        agent = AgentComponent(
            tools=tools,
            input_value=input_value,
            api_key=api_key,
            model_name="gpt-4o",
            agent_llm="OpenAI",
            temperature=temperature,
            _session_id=str(uuid4()),
        )

        response = await agent.message_response()
        assert "4" in response.data.get("text")

    @pytest.mark.api_key_required
    @pytest.mark.no_blockbuster
    async def test_agent_component_with_all_openai_models(self):
        # Mock inputs
        from tests.api_keys import get_openai_api_key

        api_key = get_openai_api_key()
        input_value = "What is 2 + 2?"

        # Iterate over all OpenAI models
        failed_models = []
        for model_name in OPENAI_CHAT_MODEL_NAMES + OPENAI_REASONING_MODEL_NAMES:
            # Initialize the AgentComponent with mocked inputs
            tools = [CalculatorToolComponent().build_tool()]  # Use the Calculator component as a tool
            agent = AgentComponent(
                tools=tools,
                input_value=input_value,
                api_key=api_key,
                model_name=model_name,
                agent_llm="OpenAI",
                _session_id=str(uuid4()),
            )

            response = await agent.message_response()
            if "4" not in response.data.get("text"):
                failed_models.append(model_name)

        assert not failed_models, f"The following models failed the test: {failed_models}"

    @pytest.mark.api_key_required
    @pytest.mark.no_blockbuster
    async def test_agent_component_with_all_anthropic_models(self):
        # Mock inputs
        api_key = os.getenv("ANTHROPIC_API_KEY")
        input_value = "What is 2 + 2?"

        # Iterate over all Anthropic models
        failed_models = {}

        for model_name in ANTHROPIC_MODELS:
            try:
                # Initialize the AgentComponent with mocked inputs
                tools = [CalculatorToolComponent().build_tool()]
                agent = AgentComponent(
                    tools=tools,
                    input_value=input_value,
                    api_key=api_key,
                    model_name=model_name,
                    agent_llm="Anthropic",
                    _session_id=str(uuid4()),
                )

                response = await agent.message_response()
                response_text = response.data.get("text", "")

                if "4" not in response_text:
                    failed_models[model_name] = f"Expected '4' in response but got: {response_text}"
            except Exception as e:
                failed_models[model_name] = f"Exception occurred: {e!s}"

            try:
                # Test with empty string input
                tools = [CalculatorToolComponent().build_tool()]
                agent = AgentComponent(
                    tools=tools,
                    input_value=" ",
                    api_key=api_key,
                    model_name=model_name,
                    agent_llm="Anthropic",
                    _session_id=str(uuid4()),
                )

                response = await agent.message_response()
                response_text = response.data.get("text", "")

            except Exception as e:
                failed_models[model_name] = f"Exception occurred: {e!s}"

        assert not failed_models, "The following models failed the test:\n" + "\n".join(
            f"{model}: {error}" for model, error in failed_models.items()
        )

    @pytest.mark.api_key_required
    @pytest.mark.no_blockbuster
    async def test_agent_handles_empty_input_with_openai(self):
        """Test that Agent component handles empty input value without errors with OpenAI."""
        api_key = os.getenv("OPENAI_API_KEY")
        tools = [CalculatorToolComponent().build_tool()]

        # Test with empty string input
        agent = AgentComponent(
            tools=tools,
            input_value="",
            api_key=api_key,
            model_name="gpt-4o",
            agent_llm="OpenAI",
            temperature=0.1,
            _session_id=str(uuid4()),
        )

        # This should not raise an error - the agent should provide a default input
        response = await agent.message_response()
        assert response is not None
        assert hasattr(response, "text") or hasattr(response, "data")

    @pytest.mark.api_key_required
    @pytest.mark.no_blockbuster
    async def test_agent_handles_whitespace_input_with_openai(self):
        """Test that Agent component handles whitespace-only input without errors with OpenAI."""
        api_key = os.getenv("OPENAI_API_KEY")
        tools = [CalculatorToolComponent().build_tool()]

        # Test with whitespace-only input
        agent = AgentComponent(
            tools=tools,
            input_value="   \n\t  ",
            api_key=api_key,
            model_name="gpt-4o",
            agent_llm="OpenAI",
            temperature=0.1,
            _session_id=str(uuid4()),
        )

        # This should not raise an error - the agent should provide a default input
        response = await agent.message_response()
        assert response is not None
        assert hasattr(response, "text") or hasattr(response, "data")

    @pytest.mark.api_key_required
    @pytest.mark.no_blockbuster
    async def test_agent_receives_string_from_message_object_with_openai(self):
        """Test that agent receives string input from Message object with actual OpenAI call.

        This test verifies the fix for the issue where agents were receiving:
        content='hi how are you' additional_kwargs={} response_metadata={}
        instead of just the string 'hi how are you'.
        """
        api_key = os.getenv("OPENAI_API_KEY")
        from lfx.schema.message import Message

        # Create a Message object as input (simulating ChatInput component output)
        message_input = Message(text="What is 5 + 3?", sender="User", sender_name="User")

        tools = [CalculatorToolComponent().build_tool()]
        agent = AgentComponent(
            tools=tools,
            input_value=message_input,  # Pass Message object, not string
            api_key=api_key,
            model_name="gpt-4o",
            agent_llm="OpenAI",
            temperature=0.1,
            _session_id=str(uuid4()),
        )

        # This should work correctly - the agent should extract text from the Message
        response = await agent.message_response()
        assert response is not None
        assert "8" in response.data.get("text", "")

    @pytest.mark.api_key_required
    @pytest.mark.no_blockbuster
    async def test_agent_receives_string_from_message_object_with_anthropic(self):
        """Test that agent receives string input from Message object with actual Anthropic call."""
        api_key = os.getenv("ANTHROPIC_API_KEY")
        from lfx.base.models.anthropic_constants import ANTHROPIC_MODELS_DETAILED
        from lfx.schema.message import Message

        # Create a Message object as input (simulating ChatInput component output)
        message_input = Message(text="What is 7 + 2?", sender="User", sender_name="User")

        tools = [CalculatorToolComponent().build_tool()]
        agent = AgentComponent(
            tools=tools,
            input_value=message_input,  # Pass Message object, not string
            api_key=api_key,
            model_name=ANTHROPIC_MODELS_DETAILED[0]["name"],
            agent_llm="Anthropic",
            _session_id=str(uuid4()),
        )

        # This should work correctly - the agent should extract text from the Message
        response = await agent.message_response()
        assert response is not None
        assert "9" in response.data.get("text", "")

    @pytest.mark.api_key_required
    @pytest.mark.no_blockbuster
    async def test_agent_handles_empty_input_with_anthropic(self):
        """Test that Agent component handles empty input value without errors with Anthropic.

        This test specifically addresses the issue:
        'messages.2: all messages must have non-empty content'
        """
        api_key = os.getenv("ANTHROPIC_API_KEY")
        tools = [CalculatorToolComponent().build_tool()]

        # Test with empty string input - this previously caused the error
        agent = AgentComponent(
            tools=tools,
            input_value="",
            api_key=api_key,
            model_name="claude-3-5-sonnet-20241022",
            agent_llm="Anthropic",
            _session_id=str(uuid4()),
        )

        # This should not raise the "messages.2: all messages must have non-empty content" error
        try:
            response = await agent.message_response()
            assert response is not None
            assert hasattr(response, "text") or hasattr(response, "data")
        except Exception as e:
            # If an error occurs, make sure it's NOT the empty content error
            error_message = str(e)
            assert "messages.2" not in error_message, f"Empty content error still occurs: {error_message}"
            assert "must have non-empty content" not in error_message, (
                f"Empty content error still occurs: {error_message}"
            )
            # Re-raise if it's a different error
            raise

    @pytest.mark.api_key_required
    @pytest.mark.no_blockbuster
    async def test_agent_handles_whitespace_input_with_anthropic(self):
        """Test that Agent component handles whitespace-only input without errors with Anthropic."""
        api_key = os.getenv("ANTHROPIC_API_KEY")
        tools = [CalculatorToolComponent().build_tool()]
        from lfx.base.models.anthropic_constants import ANTHROPIC_MODELS_DETAILED

        # Test with whitespace-only input
        agent = AgentComponent(
            tools=tools,
            input_value="   \n\t  ",
            api_key=api_key,
            model_name=ANTHROPIC_MODELS_DETAILED[0]["name"],
            agent_llm="Anthropic",
            _session_id=str(uuid4()),
        )

        # This should not raise the "messages.2: all messages must have non-empty content" error
        try:
            response = await agent.message_response()
            assert response is not None
            assert hasattr(response, "text") or hasattr(response, "data")
        except Exception as e:
            # If an error occurs, make sure it's NOT the empty content error
            error_message = str(e)
            assert "messages.2" not in error_message, f"Empty content error still occurs: {error_message}"
            assert "must have non-empty content" not in error_message, (
                f"Empty content error still occurs: {error_message}"
            )
            # Re-raise if it's a different error
            raise

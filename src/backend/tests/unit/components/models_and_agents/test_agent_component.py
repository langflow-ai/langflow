import os
from typing import Any
from unittest.mock import patch
from uuid import uuid4

import pytest
from langflow.custom import Component
from lfx.base.models.anthropic_constants import ANTHROPIC_MODELS
from lfx.base.models.openai_constants import (
    OPENAI_CHAT_MODEL_NAMES,
    OPENAI_REASONING_MODEL_NAMES,
)
from lfx.components.models_and_agents import AgentComponent
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
            "model": MockLanguageModel(),
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

    async def test_max_tokens_input_field_present(self, component_class, default_kwargs):
        """Test that max_tokens input field is present in the agent component."""
        component = await self.component_setup(component_class, default_kwargs)

        input_names = [inp.name for inp in component.inputs if hasattr(inp, "name")]

        # Verify max_tokens field exists
        assert "max_tokens" in input_names, "max_tokens input field should be present"

        # Verify the component has the attribute
        assert hasattr(component, "max_tokens"), "Component should have max_tokens attribute"

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

    async def test_agent_handles_multimodal_message_input(self, component_class, default_kwargs):
        """Test that agent properly extracts text from multimodal Message objects."""
        from lfx.schema.message import Message

        # Create a Message object with text content (no actual files for testing)
        message = Message(text="What is in this image?", sender="User", sender_name="User")

        # Set up the component
        default_kwargs["input_value"] = message
        _ = await self.component_setup(component_class, default_kwargs)

        # Convert to LangChain message
        lc_message = message.to_lc_message()

        # Test the input extraction logic for different content types
        if hasattr(lc_message, "content"):
            if isinstance(lc_message.content, str):
                # Simple string content
                assert lc_message.content == "What is in this image?"
                assert isinstance(lc_message.content, str)
            elif isinstance(lc_message.content, list):
                # Multimodal content - extract text parts
                text_parts = [item.get("text", "") for item in lc_message.content if item.get("type") == "text"]
                extracted_text = " ".join(text_parts) if text_parts else ""
                assert isinstance(extracted_text, str)
                # Verify we got text, not a message object
                assert "additional_kwargs" not in extracted_text
                assert "response_metadata" not in extracted_text

    async def test_watsonx_input_fields_present(self, component_class, default_kwargs):
        """Test that IBM WatsonX input fields are present in the component."""
        component = await self.component_setup(component_class, default_kwargs)

        input_names = [inp.name for inp in component.inputs if hasattr(inp, "name")]

        # Test for WatsonX fields
        assert "base_url_ibm_watsonx" in input_names
        assert "project_id" in input_names

    async def test_watsonx_fields_hidden_by_default(self, component_class, default_kwargs):
        """Test that WatsonX fields are hidden by default."""
        component = await self.component_setup(component_class, default_kwargs)

        # Find the WatsonX input fields
        watsonx_url_input = next(
            (inp for inp in component.inputs if hasattr(inp, "name") and inp.name == "base_url_ibm_watsonx"), None
        )
        project_id_input = next(
            (inp for inp in component.inputs if hasattr(inp, "name") and inp.name == "project_id"), None
        )

        assert watsonx_url_input is not None
        assert project_id_input is not None
        assert watsonx_url_input.show is False
        assert project_id_input.show is False

    @patch("lfx.components.models_and_agents.agent.get_language_model_options")
    async def test_update_build_config_shows_watsonx_fields(self, mock_opts, component_class, default_kwargs):
        """Test that update_build_config shows WatsonX fields when IBM WatsonX is selected."""
        from lfx.schema.dotdict import dotdict

        # Simulate selecting an IBM WatsonX model
        watsonx_model_value = [
            {
                "name": "ibm/granite-13b-chat-v2",
                "provider": "IBM WatsonX",
                "icon": "IBM",
                "metadata": {
                    "model_class": "ChatWatsonx",
                    "model_name_param": "model_id",
                    "api_key_param": "apikey",
                },
            }
        ]
        mock_opts.return_value = watsonx_model_value

        component = await self.component_setup(component_class, default_kwargs)

        # Get the frontend node to get the build_config
        frontend_node = component.to_frontend_node()
        build_config = frontend_node["data"]["node"]["template"]

        # Call update_build_config with WatsonX model selected
        updated_config = await component.update_build_config(
            dotdict(build_config), watsonx_model_value, field_name="model"
        )

        # Verify WatsonX fields are now shown
        assert updated_config["base_url_ibm_watsonx"]["show"] is True
        assert updated_config["project_id"]["show"] is True
        assert updated_config["base_url_ibm_watsonx"]["required"] is False
        assert updated_config["project_id"]["required"] is False

    @patch("lfx.components.models_and_agents.agent.get_language_model_options")
    async def test_update_build_config_hides_watsonx_fields_for_other_providers(
        self, mock_opts, component_class, default_kwargs
    ):
        """Test that update_build_config hides WatsonX fields when other providers are selected."""
        from lfx.schema.dotdict import dotdict

        # Simulate selecting an OpenAI model
        openai_model_value = [
            {
                "name": "gpt-4o",
                "provider": "OpenAI",
                "icon": "OpenAI",
                "metadata": {
                    "model_class": "ChatOpenAI",
                    "model_name_param": "model",
                    "api_key_param": "api_key",
                },
            }
        ]
        mock_opts.return_value = openai_model_value

        component = await self.component_setup(component_class, default_kwargs)

        # Get the frontend node to get the build_config
        frontend_node = component.to_frontend_node()
        build_config = frontend_node["data"]["node"]["template"]

        # Call update_build_config with OpenAI model selected
        updated_config = await component.update_build_config(
            dotdict(build_config), openai_model_value, field_name="model"
        )

        # Verify WatsonX fields are hidden
        assert updated_config["base_url_ibm_watsonx"]["show"] is False
        assert updated_config["project_id"]["show"] is False

    async def test_get_agent_requirements_passes_watsonx_params(self, component_class, default_kwargs):
        """Test that get_agent_requirements passes WatsonX URL and project_id to get_llm()."""
        from unittest.mock import AsyncMock, patch

        component = await self.component_setup(component_class, default_kwargs)

        # Set WatsonX-specific attributes
        component.base_url_ibm_watsonx = "https://us-south.ml.cloud.ibm.com"
        component.project_id = "test-project-id"
        component.model = [
            {
                "name": "ibm/granite-13b-chat-v2",
                "provider": "IBM WatsonX",
                "metadata": {
                    "model_class": "ChatWatsonx",
                    "model_name_param": "model_id",
                    "api_key_param": "apikey",
                },
            }
        ]
        component.api_key = "test-api-key"

        # Mock get_llm to capture the arguments
        with patch("lfx.components.models_and_agents.agent.get_llm") as mock_get_llm:
            mock_get_llm.return_value = MockLanguageModel()

            # Mock other required methods
            component.get_memory_data = AsyncMock(return_value=[])
            component._get_shared_callbacks = list
            component.set_tools_callbacks = lambda *_: None

            await component.get_agent_requirements()

            # Verify get_llm was called with WatsonX parameters
            mock_get_llm.assert_called_once()
            call_kwargs = mock_get_llm.call_args.kwargs
            assert call_kwargs.get("watsonx_url") == "https://us-south.ml.cloud.ibm.com"
            assert call_kwargs.get("watsonx_project_id") == "test-project-id"

    @patch("lfx.components.models_and_agents.agent.get_language_model_options")
    @patch("lfx.components.models_and_agents.agent.get_llm")
    async def test_get_agent_requirements_supports_legacy_agent_llm_model_name(
        self, mock_get_llm, mock_get_options, component_class, default_kwargs
    ):
        """Legacy agent_llm/model_name inputs should still resolve to a valid model selection."""
        from unittest.mock import AsyncMock

        default_kwargs["model"] = ""
        component = await self.component_setup(component_class, default_kwargs)
        component.agent_llm = "OpenAI"
        component.model_name = "gpt-4o"
        component.get_memory_data = AsyncMock(return_value=[])
        component._get_shared_callbacks = list
        component.set_tools_callbacks = lambda *_: None
        mock_get_options.return_value = [
            {
                "name": "gpt-4o",
                "provider": "OpenAI",
                "metadata": {
                    "model_class": "ChatOpenAI",
                    "model_name_param": "model",
                    "api_key_param": "api_key",
                },
            }
        ]
        mock_get_llm.return_value = MockLanguageModel()

        await component.get_agent_requirements()

        assert mock_get_llm.call_args.kwargs["model"] == [mock_get_options.return_value[0]]

    @patch("lfx.components.models_and_agents.agent.get_llm")
    async def test_get_agent_requirements_accepts_connected_model_instance(
        self, mock_get_llm, component_class, default_kwargs
    ):
        """Connected BaseLanguageModel instances should bypass model-selection validation."""
        from unittest.mock import AsyncMock

        connected_model = MockLanguageModel()
        default_kwargs["model"] = connected_model
        component = await self.component_setup(component_class, default_kwargs)
        component.get_memory_data = AsyncMock(return_value=[])
        component._get_shared_callbacks = list
        component.set_tools_callbacks = lambda *_: None
        mock_get_llm.return_value = connected_model

        llm_model, _, _ = await component.get_agent_requirements()

        assert llm_model is connected_model
        assert mock_get_llm.call_args.kwargs["model"] is connected_model

    @patch("lfx.components.models_and_agents.agent.AgentComponent.get_memory_data")
    @patch("lfx.components.models_and_agents.agent.get_llm")
    async def test_agent_passes_max_tokens_to_get_llm(
        self, mock_get_llm, mock_get_memory_data, component_class, default_kwargs
    ):
        """Test that agent component passes max_tokens parameter to get_llm function."""
        from unittest.mock import AsyncMock, MagicMock

        mock_get_memory_data.return_value = AsyncMock(return_value=[])

        # Setup mock
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm

        # Set max_tokens in default_kwargs
        default_kwargs["max_tokens"] = 500

        component = await self.component_setup(component_class, default_kwargs)

        # validate_model_selection requires a list — set a valid model selection
        component.model = [{"name": "gpt-4o", "provider": "OpenAI", "metadata": {}}]

        # Call get_agent_requirements which internally calls get_llm
        await component.get_agent_requirements()

        # Verify get_llm was called with max_tokens
        mock_get_llm.assert_called_once()
        call_kwargs = mock_get_llm.call_args.kwargs

        assert "max_tokens" in call_kwargs, "max_tokens should be passed to get_llm"
        assert call_kwargs["max_tokens"] == 500

    @patch("lfx.components.models_and_agents.agent.AgentComponent.get_memory_data")
    @patch("lfx.components.models_and_agents.agent.get_llm")
    async def test_agent_passes_none_max_tokens_when_not_set(
        self, mock_get_llm, mock_get_memory_data, component_class, default_kwargs
    ):
        """Test that agent component passes None for max_tokens when not set."""
        from unittest.mock import AsyncMock, MagicMock

        mock_get_memory_data.return_value = AsyncMock(return_value=[])

        # Setup mock
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm

        # Don't set max_tokens in default_kwargs - ensure it's not present
        if "max_tokens" in default_kwargs:
            del default_kwargs["max_tokens"]

        component = await self.component_setup(component_class, default_kwargs)

        # validate_model_selection requires a list — set a valid model selection
        component.model = [{"name": "gpt-4o", "provider": "OpenAI", "metadata": {}}]

        # Call get_agent_requirements which internally calls get_llm
        await component.get_agent_requirements()

        # Verify get_llm was called
        mock_get_llm.assert_called_once()

        # Access kwargs using the .kwargs attribute (more reliable than indexing)
        call_kwargs = mock_get_llm.call_args.kwargs

        # max_tokens should be passed as None when not set
        assert "max_tokens" in call_kwargs, "max_tokens should be passed to get_llm even when None"
        assert call_kwargs["max_tokens"] is None

    @patch("lfx.components.models_and_agents.agent.AgentComponent.get_memory_data")
    @patch("lfx.components.models_and_agents.agent.get_llm")
    async def test_agent_max_tokens_with_provider_specific_field_name(
        self, mock_get_llm, mock_get_memory_data, component_class, default_kwargs
    ):
        """Test that agent component passes max_tokens which will be handled by provider-specific field names."""
        from unittest.mock import AsyncMock, MagicMock

        mock_get_memory_data.return_value = AsyncMock(return_value=[])

        # Setup mock
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm

        # Set max_tokens; get_llm uses model metadata for provider-specific field names (e.g. max_output_tokens)
        default_kwargs["max_tokens"] = 1000

        component = await self.component_setup(component_class, default_kwargs)

        # validate_model_selection requires a list — set a valid model selection
        component.model = [{"name": "gpt-4o", "provider": "OpenAI", "metadata": {}}]

        # Call get_agent_requirements which internally calls get_llm
        await component.get_agent_requirements()

        # Verify get_llm was called with max_tokens
        mock_get_llm.assert_called_once()
        call_kwargs = mock_get_llm.call_args.kwargs

        assert "max_tokens" in call_kwargs, "max_tokens should be passed to get_llm"
        assert call_kwargs["max_tokens"] == 1000
        # Note: The provider-specific field name mapping happens inside get_llm,
        # so we just verify max_tokens is passed correctly


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
            model=[
                {
                    "name": "gpt-4o",
                    "provider": "OpenAI",
                    "icon": "OpenAI",
                    "metadata": {
                        "model_class": "ChatOpenAI",
                        "model_name_param": "model",
                        "api_key_param": "api_key",
                    },
                }
            ],
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
                model=[
                    {
                        "name": model_name,
                        "provider": "OpenAI",
                        "icon": "OpenAI",
                        "metadata": {
                            "model_class": "ChatOpenAI",
                            "model_name_param": "model",
                            "api_key_param": "api_key",
                        },
                    }
                ],
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
                    model=[
                        {
                            "name": model_name,
                            "provider": "Anthropic",
                            "icon": "Anthropic",
                            "metadata": {
                                "model_class": "ChatAnthropic",
                                "model_name_param": "model",
                                "api_key_param": "api_key",
                            },
                        }
                    ],
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
                    model=[
                        {
                            "name": model_name,
                            "provider": "Anthropic",
                            "icon": "Anthropic",
                            "metadata": {
                                "model_class": "ChatAnthropic",
                                "model_name_param": "model",
                                "api_key_param": "api_key",
                            },
                        }
                    ],
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
            model=[
                {
                    "name": "gpt-4o",
                    "provider": "OpenAI",
                    "icon": "OpenAI",
                    "metadata": {
                        "model_class": "ChatOpenAI",
                        "model_name_param": "model",
                        "api_key_param": "api_key",
                    },
                }
            ],
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
            model=[
                {
                    "name": "gpt-4o",
                    "provider": "OpenAI",
                    "icon": "OpenAI",
                    "metadata": {
                        "model_class": "ChatOpenAI",
                        "model_name_param": "model",
                        "api_key_param": "api_key",
                    },
                }
            ],
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
            model=[
                {
                    "name": "claude-3-5-sonnet-20241022",
                    "provider": "Anthropic",
                    "icon": "Anthropic",
                    "metadata": {
                        "model_class": "ChatAnthropic",
                        "model_name_param": "model",
                        "api_key_param": "api_key",
                    },
                }
            ],
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
            model=[
                {
                    "name": ANTHROPIC_MODELS_DETAILED[0]["name"],
                    "provider": "Anthropic",
                    "icon": "Anthropic",
                    "metadata": {
                        "model_class": "ChatAnthropic",
                        "model_name_param": "model",
                        "api_key_param": "api_key",
                    },
                }
            ],
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

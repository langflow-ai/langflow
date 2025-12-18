import os
from typing import Any
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

    @pytest.mark.skip(reason="Test marked as skipped, agent dual output removed")
    async def test_agent_has_dual_outputs(self, component_class, default_kwargs):
        """Test that Agent component has both Response and Structured Response outputs."""
        component = await self.component_setup(component_class, default_kwargs)

        assert len(component.outputs) == 2
        assert component.outputs[0].name == "response"
        assert component.outputs[0].display_name == "Response"
        assert component.outputs[0].method == "message_response"

        assert component.outputs[1].name == "structured_response"
        assert component.outputs[1].display_name == "Structured Response"
        assert component.outputs[1].method == "json_response"
        assert component.outputs[1].tool_mode is False

    @pytest.mark.skip(reason="Test marked as skipped, agent dual output removed")
    async def test_json_mode_filtered_from_openai_inputs(self, component_class, default_kwargs):
        """Test that json_mode is filtered out from OpenAI inputs."""
        component = await self.component_setup(component_class, default_kwargs)

        # Check that json_mode is not in the agent's inputs
        input_names = [inp.name for inp in component.inputs if hasattr(inp, "name")]
        assert "json_mode" not in input_names

        # Verify other inputs are still present
        assert "model" in input_names
        assert "api_key" in input_names

    @pytest.mark.skip(reason="Test marked as skipped, agent dual output removed")
    async def test_json_response_parsing_valid_json(self, component_class, default_kwargs):
        """Test that json_response correctly parses JSON from agent response."""
        component = await self.component_setup(component_class, default_kwargs)
        # Mock the get_agent_requirements method to avoid actual LLM calls
        from unittest.mock import AsyncMock

        component.get_agent_requirements = AsyncMock(return_value=(MockLanguageModel(), [], []))
        component.create_agent_runnable = AsyncMock(return_value=None)
        mock_result = type("MockResult", (), {"content": '{"name": "test", "value": 123}'})()
        component.run_agent = AsyncMock(return_value=mock_result)

        result = await component.json_response()

        from lfx.schema.data import Data

        assert isinstance(result, Data)
        assert result.data == {"name": "test", "value": 123}

    @pytest.mark.skip(reason="Test marked as skipped, agent dual output removed")
    async def test_json_response_parsing_embedded_json(self, component_class, default_kwargs):
        """Test that json_response handles text containing JSON."""
        component = await self.component_setup(component_class, default_kwargs)
        # Mock the get_agent_requirements method to avoid actual LLM calls
        from unittest.mock import AsyncMock

        component.get_agent_requirements = AsyncMock(return_value=(MockLanguageModel(), [], []))
        component.create_agent_runnable = AsyncMock(return_value=None)
        mock_result = type("MockResult", (), {"content": 'Here is the result: {"status": "success"} - done!'})()
        component.run_agent = AsyncMock(return_value=mock_result)

        result = await component.json_response()

        from lfx.schema.data import Data

        assert isinstance(result, Data)
        assert result.data == {"status": "success"}

    @pytest.mark.skip(reason="Test marked as skipped, agent dual output removed")
    async def test_json_response_error_handling(self, component_class, default_kwargs):
        """Test that json_response handles completely non-JSON responses."""
        component = await self.component_setup(component_class, default_kwargs)
        # Mock the get_agent_requirements method to avoid actual LLM calls
        from unittest.mock import AsyncMock

        component.get_agent_requirements = AsyncMock(return_value=(MockLanguageModel(), [], []))
        component.create_agent_runnable = AsyncMock(return_value=None)
        mock_result = type("MockResult", (), {"content": "This is just plain text with no JSON"})()
        component.run_agent = AsyncMock(return_value=mock_result)

        result = await component.json_response()

        from lfx.schema.data import Data

        assert isinstance(result, Data)
        assert "error" in result.data
        assert result.data["content"] == "This is just plain text with no JSON"

    @pytest.mark.skip(reason="Test marked as skipped, agent dual output removed")
    async def test_model_building_without_json_mode(self, component_class, default_kwargs):
        """Test that model building works without json_mode attribute."""
        component = await self.component_setup(component_class, default_kwargs)
        component.model = "OpenAI"

        # Mock component for testing
        from unittest.mock import Mock

        mock_component = Mock()
        mock_component.set.return_value = mock_component

        # Should not raise AttributeError for missing json_mode
        result = component.set_component_params(mock_component)

        assert result is not None
        # Verify set was called (meaning no AttributeError occurred)
        mock_component.set.assert_called_once()

    @pytest.mark.skip(reason="Test marked as skipped, agent dual output removed")
    async def test_json_response_with_schema_validation(self, component_class, default_kwargs):
        """Test that json_response validates against provided schema."""
        # Set up component with output schema
        default_kwargs["output_schema"] = [
            {"name": "name", "type": "str", "description": "Name field", "multiple": False},
            {"name": "age", "type": "int", "description": "Age field", "multiple": False},
        ]
        component = await self.component_setup(component_class, default_kwargs)
        # Mock the get_agent_requirements method
        from unittest.mock import AsyncMock

        component.get_agent_requirements = AsyncMock(return_value=(MockLanguageModel(), [], []))
        component.create_agent_runnable = AsyncMock(return_value=None)
        mock_result = type("MockResult", (), {"content": '{"name": "John", "age": 25}'})()
        component.run_agent = AsyncMock(return_value=mock_result)

        result = await component.json_response()

        from langflow.schema.data import Data

        assert isinstance(result, Data)
        assert result.data == {"name": "John", "age": 25}

    @pytest.mark.skip(reason="Test marked as skipped, agent dual output removed")
    async def test_agent_component_initialization(self, component_class, default_kwargs):
        """Test that Agent component initializes correctly with filtered inputs."""
        component = await self.component_setup(component_class, default_kwargs)

        # Should not raise any errors during initialization
        assert component.display_name == "Agent"
        assert component.name == "Agent"
        assert len(component.inputs) > 0
        assert len(component.outputs) == 2

    @pytest.mark.skip(reason="Test marked as skipped, agent dual output removed")
    async def test_frontend_node_structure(self, component_class, default_kwargs):
        """Test that frontend node has correct structure with filtered inputs."""
        component = await self.component_setup(component_class, default_kwargs)

        frontend_node = component.to_frontend_node()
        build_config = frontend_node["data"]["node"]["template"]

        # Verify json_mode is not in build config
        assert "json_mode" not in build_config

        # Verify other expected fields are present
        assert "model" in build_config
        assert "system_prompt" in build_config
        assert "add_current_date_tool" in build_config

    @pytest.mark.skip(reason="Test marked as skipped, agent dual output removed")
    async def test_preprocess_schema(self, component_class, default_kwargs):
        """Test that _preprocess_schema correctly handles schema validation."""
        component = await self.component_setup(component_class, default_kwargs)

        # Test schema preprocessing
        raw_schema = [
            {"name": "field1", "type": "str", "description": "Test field", "multiple": "true"},
            {"name": "field2", "type": "int", "description": "Another field", "multiple": False},
        ]

        processed = component._preprocess_schema(raw_schema)

        assert len(processed) == 2
        assert processed[0]["multiple"] is True  # String "true" should be converted to bool
        assert processed[1]["multiple"] is False

    @pytest.mark.skip(reason="Test marked as skipped, agent dual output removed")
    async def test_build_structured_output_base_with_validation(self, component_class, default_kwargs):
        """Test build_structured_output_base with schema validation."""
        default_kwargs["output_schema"] = [
            {"name": "name", "type": "str", "description": "Name field", "multiple": False},
            {"name": "count", "type": "int", "description": "Count field", "multiple": False},
        ]
        component = await self.component_setup(component_class, default_kwargs)

        # Test valid JSON that matches schema
        valid_content = '{"name": "test", "count": 42}'
        result = await component.build_structured_output_base(valid_content)
        assert result == [{"name": "test", "count": 42}]

    @pytest.mark.skip(reason="Test marked as skipped, agent dual output removed")
    async def test_build_structured_output_base_without_schema(self, component_class, default_kwargs):
        """Test build_structured_output_base without schema validation."""
        component = await self.component_setup(component_class, default_kwargs)

        # Test with no output_schema
        content = '{"any": "data", "number": 123}'
        result = await component.build_structured_output_base(content)
        assert result == {"any": "data", "number": 123}

    @pytest.mark.skip(reason="Test marked as skipped, agent dual output removed")
    async def test_build_structured_output_base_embedded_json(self, component_class, default_kwargs):
        """Test extraction of JSON from embedded text."""
        component = await self.component_setup(component_class, default_kwargs)

        content = 'Here is some text with {"embedded": "json"} inside it.'
        result = await component.build_structured_output_base(content)
        assert result == {"embedded": "json"}

    @pytest.mark.skip(reason="Test marked as skipped, agent dual output removed")
    async def test_build_structured_output_base_no_json(self, component_class, default_kwargs):
        """Test handling of content with no JSON."""
        component = await self.component_setup(component_class, default_kwargs)

        content = "This is just plain text with no JSON at all."
        result = await component.build_structured_output_base(content)
        assert "error" in result
        assert result["content"] == content

    @pytest.mark.skip(reason="Test marked as skipped, agent dual output removed")
    async def test_new_input_fields_present(self, component_class, default_kwargs):
        """Test that new input fields are present in the component."""
        component = await self.component_setup(component_class, default_kwargs)

        input_names = [inp.name for inp in component.inputs if hasattr(inp, "name")]

        # Test for new fields
        assert "format_instructions" in input_names
        assert "output_schema" in input_names
        assert "n_messages" in input_names

        # Verify default values
        assert hasattr(component, "format_instructions")
        assert hasattr(component, "output_schema")
        assert hasattr(component, "n_messages")
        assert component.n_messages == 100

    @pytest.mark.skip(reason="Test marked as skipped, agent dual output removed")
    async def test_agent_has_correct_outputs(self, component_class, default_kwargs):
        """Test that Agent component has the correct output configuration."""
        component = await self.component_setup(component_class, default_kwargs)

        assert len(component.outputs) == 2

        # Test response output
        response_output = component.outputs[0]
        assert response_output.name == "response"
        assert response_output.display_name == "Response"
        assert response_output.method == "message_response"

        # Test structured response output
        structured_output = component.outputs[1]
        assert structured_output.name == "structured_response"
        assert structured_output.display_name == "Structured Response"
        assert structured_output.method == "json_response"
        assert structured_output.tool_mode is False

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

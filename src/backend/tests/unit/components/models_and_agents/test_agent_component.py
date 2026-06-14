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
            "add_calculator_tool": True,
            "model": MockLanguageModel(),
            "handle_parsing_errors": True,
            "input_value": "",
            "max_iterations": 10,
            "system_prompt": "You are a helpful assistant.",
            "tools": [],
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

    @patch("lfx.base.models.unified_models.get_language_model_options")
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

    @patch("lfx.base.models.unified_models.get_language_model_options")
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

    async def test_should_expose_stream_input_when_agent_component_is_loaded(self, component_class, default_kwargs):
        """Regression: the Stream toggle disappeared from the Agent after the ModelInput unification (#12025).

        Given the Agent component is loaded, When its inputs are inspected,
        Then a 'stream' input field must be present so users can control LLM streaming.
        """
        component = await self.component_setup(component_class, default_kwargs)

        input_names = [inp.name for inp in component.inputs if hasattr(inp, "name")]

        assert "stream" in input_names, "stream input field should be present on the Agent component"
        assert hasattr(component, "stream"), "Component should have a stream attribute"

    async def test_should_default_stream_input_value_to_true_when_agent_loaded(self, component_class, default_kwargs):
        """Regression guard for PR #13358: the ``stream`` BoolInput default MUST be True.

        If a future refactor flips the default back to False (as it was between PR #13155
        and PR #13358), new flows created from the bare AgentComponent will save
        ``stream=False`` and silently lose Playground live-typing. The fix in
        ``_get_llm`` hard-codes stream=True regardless of the toggle, but the
        UI-facing default must STILL be True so users don't see a misleading
        OFF state in the inspector.
        """
        component = await self.component_setup(component_class, default_kwargs)

        stream_input = next((inp for inp in component.inputs if getattr(inp, "name", None) == "stream"), None)
        assert stream_input is not None, "stream BoolInput must exist on AgentComponent"
        assert getattr(stream_input, "value", None) is True, (
            "AgentComponent.inputs[stream].value must default to True. "
            "Flipping this default reintroduces the regression that PR #13358 fixed."
        )
        assert getattr(stream_input, "advanced", False) is True, (
            "stream toggle is hidden under Advanced so users don't accidentally disable it."
        )

    @patch("lfx.components.models_and_agents.agent.AgentComponent.get_memory_data")
    @patch("lfx.components.models_and_agents.agent.get_llm")
    async def test_should_force_stream_true_to_get_llm_even_when_toggle_is_false(
        self, mock_get_llm, mock_get_memory_data, component_class, default_kwargs
    ):
        """Streaming is mandatory: even if a saved flow has ``stream=False``, the LLM must stream.

        Belt-and-suspenders against the PR-#13155 regression: even if a future change
        accidentally re-wires ``_get_llm`` to read ``self.stream`` (and the saved value
        is False), the contract is that ``get_llm`` MUST receive ``stream=True`` so the
        chat model is built with ``streaming=True``. Mirror of the lfx-side test
        ``test_should_pass_stream_true_to_get_llm_when_self_stream_toggle_is_false``.
        """
        from unittest.mock import AsyncMock, MagicMock

        mock_get_memory_data.return_value = AsyncMock(return_value=[])
        mock_get_llm.return_value = MagicMock()

        default_kwargs["stream"] = False
        component = await self.component_setup(component_class, default_kwargs)
        component.model = [{"name": "gpt-4o", "provider": "OpenAI", "metadata": {}}]

        await component.get_agent_requirements()

        mock_get_llm.assert_called_once()
        call_kwargs = mock_get_llm.call_args.kwargs
        assert call_kwargs.get("stream") is True, (
            "Agent must call get_llm with stream=True regardless of the BoolInput value. "
            f"Got stream={call_kwargs.get('stream')!r}. The Agent has no opt-out from streaming."
        )

    @patch("lfx.components.models_and_agents.agent.AgentComponent.get_memory_data")
    @patch("lfx.components.models_and_agents.agent.get_llm")
    async def test_should_pass_stream_value_to_get_llm_when_stream_input_is_enabled(
        self, mock_get_llm, mock_get_memory_data, component_class, default_kwargs
    ):
        """Regression: the Agent must forward the Stream toggle value to get_llm().

        Given stream=True on the Agent, When get_agent_requirements runs,
        Then get_llm() must be called with stream=True so the LLM streams responses.
        """
        from unittest.mock import AsyncMock, MagicMock

        mock_get_memory_data.return_value = AsyncMock(return_value=[])
        mock_get_llm.return_value = MagicMock()

        default_kwargs["stream"] = True
        component = await self.component_setup(component_class, default_kwargs)

        # validate_model_selection requires a list — set a valid model selection
        component.model = [{"name": "gpt-4o", "provider": "OpenAI", "metadata": {}}]

        await component.get_agent_requirements()

        mock_get_llm.assert_called_once()
        call_kwargs = mock_get_llm.call_args.kwargs
        assert "stream" in call_kwargs, "stream should be passed to get_llm"
        assert call_kwargs["stream"] is True

    async def test_should_append_calculator_tool_when_add_calculator_toggle_is_true(
        self, component_class, default_kwargs
    ):
        """Calculator tool is appended when the toggle is enabled.

        Given add_calculator_tool=True, When get_agent_requirements runs,
        Then self.tools contains a StructuredTool derived from CalculatorComponent.
        """
        from unittest.mock import AsyncMock

        from langchain_core.tools import StructuredTool

        default_kwargs["add_calculator_tool"] = True
        default_kwargs["add_current_date_tool"] = False  # isolate: only calculator
        component = await self.component_setup(component_class, default_kwargs)
        component.model = [{"name": "gpt-4o", "provider": "OpenAI", "metadata": {}}]
        component.get_memory_data = AsyncMock(return_value=[])
        component._get_shared_callbacks = list
        component.set_tools_callbacks = lambda *_: None

        with patch("lfx.components.models_and_agents.agent.get_llm") as mock_get_llm:
            mock_get_llm.return_value = MockLanguageModel()
            _, _, tools = await component.get_agent_requirements()

        assert len(tools) == 1
        assert isinstance(tools[0], StructuredTool)
        assert "evaluate" in tools[0].name.lower(), f"Expected a Calculator-derived tool; got name={tools[0].name!r}"

    async def test_should_not_append_calculator_tool_when_add_calculator_toggle_is_false(
        self, component_class, default_kwargs
    ):
        """Calculator tool is skipped when the toggle is disabled.

        Given add_calculator_tool=False, When get_agent_requirements runs,
        Then no Calculator tool is appended to self.tools.
        """
        from unittest.mock import AsyncMock

        default_kwargs["add_calculator_tool"] = False
        default_kwargs["add_current_date_tool"] = False
        component = await self.component_setup(component_class, default_kwargs)
        component.model = [{"name": "gpt-4o", "provider": "OpenAI", "metadata": {}}]
        component.get_memory_data = AsyncMock(return_value=[])
        component._get_shared_callbacks = list
        component.set_tools_callbacks = lambda *_: None

        with patch("lfx.components.models_and_agents.agent.get_llm") as mock_get_llm:
            mock_get_llm.return_value = MockLanguageModel()
            _, _, tools = await component.get_agent_requirements()

        assert tools == []

    async def test_should_register_calculator_tool_only_once_when_external_calculator_connected_and_toggle_enabled(
        self, component_class, default_kwargs
    ):
        """Internal toggle must not register a tool whose name already comes from an external connection.

        Bug: Agent has add_calculator_tool=True (default). When a Calculator component is also
        wired into the external Tools input, the StructuredTool 'evaluate_expression' is registered
        twice. Anthropic and Gemini reject duplicate tool names with HTTP 400
        ('Tool names must be unique' / 'Duplicate function declaration found: evaluate_expression').

        Given add_calculator_tool=True AND an external Calculator-derived tool already in self.tools,
        When get_agent_requirements runs,
        Then the resulting tools list contains 'evaluate_expression' exactly once.
        """
        from unittest.mock import AsyncMock

        from lfx.components.utilities.calculator_core import CalculatorComponent

        # An external connection delivers exactly the StructuredTool that
        # CalculatorComponent.to_toolkit() produces — re-use the same path here.
        external_calc_tool = (await CalculatorComponent().to_toolkit()).pop(0)
        assert external_calc_tool.name == "evaluate_expression"

        default_kwargs["add_calculator_tool"] = True
        default_kwargs["add_current_date_tool"] = False
        default_kwargs["tools"] = [external_calc_tool]
        component = await self.component_setup(component_class, default_kwargs)
        component.model = [{"name": "gpt-4o", "provider": "OpenAI", "metadata": {}}]
        component.get_memory_data = AsyncMock(return_value=[])
        component._get_shared_callbacks = list
        component.set_tools_callbacks = lambda *_: None

        with patch("lfx.components.models_and_agents.agent.get_llm") as mock_get_llm:
            mock_get_llm.return_value = MockLanguageModel()
            _, _, tools = await component.get_agent_requirements()

        tool_names = [t.name for t in tools]
        assert tool_names.count("evaluate_expression") == 1, (
            f"'evaluate_expression' must be registered exactly once; got {tool_names!r}. "
            "Duplicate tool names are rejected by Anthropic/Gemini with HTTP 400."
        )

    def test_should_replace_current_date_and_model_name_when_both_placeholders_present(self, component_class):
        """Unit test: helper replaces both placeholders with concrete values."""
        component = component_class()
        component.model = [{"name": "gpt-4o", "provider": "OpenAI", "metadata": {}}]

        prompt = "Today is {current_date}. You are powered by {model_name}."
        result = component._inject_dynamic_prompt_values(prompt)

        assert "{current_date}" not in result
        assert "{model_name}" not in result
        assert "gpt-4o" in result

    def test_should_leave_literal_braces_untouched_when_prompt_has_no_known_placeholders(self, component_class):
        """Adversarial: prompts with literal JSON like {"key": 1} must not raise and must stay intact."""
        component = component_class()
        component.model = [{"name": "gpt-4o", "provider": "OpenAI", "metadata": {}}]

        prompt = 'Respond with JSON: {"key": 1, "nested": {"a": [1, 2]}}.'
        result = component._inject_dynamic_prompt_values(prompt)

        assert result == prompt

    def test_should_return_empty_when_prompt_is_empty(self, component_class):
        """Edge case: empty/None prompt is returned as-is without raising."""
        component = component_class()
        assert component._inject_dynamic_prompt_values("") == ""
        assert component._inject_dynamic_prompt_values(None) is None

    async def test_should_inject_dynamic_values_into_system_prompt_when_message_response_runs(
        self, component_class, default_kwargs
    ):
        """Integration: message_response must call self.set with the resolved system_prompt."""
        from unittest.mock import AsyncMock, MagicMock

        default_kwargs["system_prompt"] = "Powered by {model_name}."
        default_kwargs["add_calculator_tool"] = False
        default_kwargs["add_current_date_tool"] = False
        component = await self.component_setup(component_class, default_kwargs)
        component.model = [{"name": "gpt-4o", "provider": "OpenAI", "metadata": {}}]
        component.get_memory_data = AsyncMock(return_value=[])
        component._get_shared_callbacks = list
        component.set_tools_callbacks = lambda *_: None

        captured: dict = {}

        def fake_set(**kwargs):
            captured.update(kwargs)
            return component

        component.set = fake_set
        component.create_agent_runnable = MagicMock(return_value=MagicMock())
        component.run_agent = AsyncMock(return_value=MagicMock())

        with patch("lfx.components.models_and_agents.agent.get_llm") as mock_get_llm:
            mock_get_llm.return_value = MockLanguageModel()
            await component.message_response()

        assert captured.get("system_prompt") == "Powered by gpt-4o."

    async def test_should_expose_structured_response_output_when_class_loaded(self, component_class):
        """The Agent must declare a 'structured_response' output wired to json_response()."""
        output_names = {o.name: o for o in component_class.outputs}

        assert "structured_response" in output_names, "Agent should expose a structured_response output"
        assert output_names["structured_response"].method == "json_response"
        assert "Data" in output_names["structured_response"].types

    async def test_should_not_mutate_format_instructions_when_json_response_runs(self, component_class, default_kwargs):
        """Regression: injection must only touch agent_instructions, not format_instructions.

        Forces the prompt-fallback path (by attaching a tool) so the augmented system
        prompt is built and passed to ``set()``. Native structured output does not
        concatenate format_instructions because the schema is enforced by the provider.
        """
        from unittest.mock import AsyncMock, MagicMock

        default_kwargs["system_prompt"] = "Powered by {model_name}."
        default_kwargs["format_instructions"] = "Return JSON with fields {current_date} and {model_name} preserved."
        default_kwargs["add_calculator_tool"] = False
        default_kwargs["add_current_date_tool"] = False
        # Non-empty schema is required to exercise the structured-output path at all.
        default_kwargs["output_schema"] = [
            {"name": "answer", "type": "str", "description": "the answer", "multiple": False},
        ]
        component = await self.component_setup(component_class, default_kwargs)
        component.model = [{"name": "gpt-4o", "provider": "OpenAI", "metadata": {}}]
        component.get_memory_data = AsyncMock(return_value=[])
        component._get_shared_callbacks = list
        component.set_tools_callbacks = lambda *_: None
        # A non-empty tools list forces the orchestrator into fallback mode (prefer_native=False),
        # which is the only path that builds the augmented system prompt asserted below.
        fake_tool = MagicMock()
        fake_tool.name = "fake_tool"
        component.tools = [fake_tool]

        captured: dict = {}

        def fake_set(**kwargs):
            captured.update(kwargs)
            return component

        component.set = fake_set
        component.create_agent_runnable = MagicMock(return_value=MagicMock())
        component.run_agent = AsyncMock(return_value=MagicMock(content='{"answer": "42"}'))

        with patch("lfx.components.models_and_agents.agent.get_llm") as mock_get_llm:
            mock_get_llm.return_value = MockLanguageModel()
            await component.json_response()

        prompt = captured.get("system_prompt") or ""
        assert "Powered by gpt-4o." in prompt, "agent_instructions should have placeholders replaced"
        assert "{current_date}" in prompt, "format_instructions literal braces must survive"
        assert "{model_name} preserved" in prompt, "format_instructions literal braces must survive"

    async def test_should_not_emit_chat_message_when_json_response_uses_fallback(self, component_class, default_kwargs):
        """Regression: fallback path must not emit a chat message via run_agent's send_message.

        Bug: when output_schema is wired to Chat Output and tools are attached, the
        playground shows two AI messages with the same JSON. run_agent streams the
        agent's final answer through self.send_message (for message_response), and
        the orchestrator-returned Data is rendered separately by the downstream
        Chat Output. In the structured-response flow, only the latter should reach
        the playground.
        """
        from unittest.mock import AsyncMock, MagicMock

        from lfx.schema.message import Message

        default_kwargs["add_calculator_tool"] = False
        default_kwargs["add_current_date_tool"] = False
        default_kwargs["output_schema"] = [
            {"name": "answer", "type": "str", "description": "the answer", "multiple": False},
        ]
        component = await self.component_setup(component_class, default_kwargs)
        component.model = [{"name": "gpt-4o", "provider": "OpenAI", "metadata": {}}]
        component.get_memory_data = AsyncMock(return_value=[])
        component._get_shared_callbacks = list
        component.set_tools_callbacks = lambda *_: None
        # A non-empty tools list forces the orchestrator into fallback mode
        # (prefer_native=False), which is the path that triggers the duplication.
        fake_tool = MagicMock()
        fake_tool.name = "fake_tool"
        component.tools = [fake_tool]

        component.set = MagicMock(return_value=component)
        component.create_agent_runnable = MagicMock(return_value=MagicMock())

        chat_emissions: list[Message] = []

        async def tracked_send_message(message, *_args, **_kwargs):
            chat_emissions.append(message)
            return message

        component.send_message = tracked_send_message

        # Reproduce production run_agent's side-effect: it streams the final
        # message through self.send_message. The fix must intercept this so the
        # fallback's intermediate output never reaches the playground.
        async def fake_run_agent(_agent_runnable):
            emitted = Message(text='{"answer": "42"}')
            await component.send_message(emitted)
            return emitted

        component.run_agent = fake_run_agent

        with patch("lfx.components.models_and_agents.agent.get_llm") as mock_get_llm:
            mock_get_llm.return_value = MockLanguageModel()
            await component.json_response()

        assert chat_emissions == [], (
            "Fallback path must suppress run_agent's chat-message emission — the "
            "Chat Output downstream renders the structured Data. "
            f"Got {len(chat_emissions)} emission(s)."
        )

    async def test_should_restore_send_message_when_run_agent_raises_in_fallback(self, component_class, default_kwargs):
        """Durability anchor: send_message suppression during fallback must be scoped.

        Even when run_agent raises, the original method must be restored on the component
        instance. Otherwise a later message_response call would silently swallow chat
        emissions.
        """
        from unittest.mock import AsyncMock, MagicMock

        default_kwargs["add_calculator_tool"] = False
        default_kwargs["add_current_date_tool"] = False
        default_kwargs["output_schema"] = [
            {"name": "answer", "type": "str", "description": "the answer", "multiple": False},
        ]
        component = await self.component_setup(component_class, default_kwargs)
        component.model = [{"name": "gpt-4o", "provider": "OpenAI", "metadata": {}}]
        component.get_memory_data = AsyncMock(return_value=[])
        component._get_shared_callbacks = list
        component.set_tools_callbacks = lambda *_: None
        # Force fallback path via attached tools (prefer_native=False).
        fake_tool = MagicMock()
        fake_tool.name = "fake_tool"
        component.tools = [fake_tool]
        component.set = MagicMock(return_value=component)
        component.create_agent_runnable = MagicMock(return_value=MagicMock())

        # Install a known sentinel so we can identity-check it after json_response.
        # (Default `component.send_message` is a bound method recreated on every access,
        # which would defeat an `is` assertion.)
        post_emissions: list[Any] = []

        async def sentinel_send_message(message, *_args, **_kwargs):
            post_emissions.append(message)
            return message

        component.send_message = sentinel_send_message

        async def exploding_run_agent(_runnable):
            msg = "boom"
            raise ValueError(msg)

        component.run_agent = exploding_run_agent

        with patch("lfx.components.models_and_agents.agent.get_llm") as mock_get_llm:
            mock_get_llm.return_value = MockLanguageModel()
            # json_response handles the exception internally and returns an error Data,
            # so the exception is swallowed gracefully — but the swap must already be undone.
            await component.json_response()

        assert component.send_message is sentinel_send_message, (
            "send_message must be restored on the component even when run_agent raises; "
            "otherwise a subsequent message_response would silently drop chat emissions."
        )
        # And the restored function must actually be callable as send_message.
        from lfx.schema.message import Message

        await component.send_message(Message(text="post-fallback"))
        assert len(post_emissions) == 1

    async def test_should_accept_add_calculator_tool_in_default_keys(self, component_class, default_kwargs):
        """update_build_config's default_keys validation must include add_calculator_tool."""
        from lfx.schema.dotdict import dotdict

        with patch("lfx.components.models_and_agents.agent.get_language_model_options") as mock_opts:
            mock_opts.return_value = [
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
            component = await self.component_setup(component_class, default_kwargs)
            frontend_node = component.to_frontend_node()
            build_config = frontend_node["data"]["node"]["template"]

            # add_calculator_tool must be present in the build_config already; if not,
            # update_build_config will error listing it as missing.
            assert "add_calculator_tool" in build_config

            updated_config = await component.update_build_config(
                dotdict(build_config), mock_opts.return_value, field_name="model"
            )
            assert "add_calculator_tool" in updated_config

    def test_should_have_placeholders_in_default_system_prompt(self, component_class):
        """Default system_prompt ships with placeholders for the dynamic injection.

        Ensures {current_date} and {model_name} are visible on a fresh agent so
        that the dynamic injection has an observable effect out-of-the-box.
        """
        prompt_input = next(
            (inp for inp in component_class.inputs if getattr(inp, "name", None) == "system_prompt"),
            None,
        )
        assert prompt_input is not None
        assert "{current_date}" in prompt_input.value
        assert "{model_name}" in prompt_input.value

    async def test_should_keep_description_in_sync_when_agent_used_as_tool(self, component_class, default_kwargs):
        """Regression for GitHub issue #9155.

        When an Agent is exposed as a tool, the deprecated agent_description
        override made the generated tool's ``description`` diverge from
        ``display_description`` on the very first build. That divergence made the
        merge logic in ``_build_tools_metadata_input()`` permanently treat the
        description as a user customization, so later changes to the agent's
        description never reached the parent agent's Actions panel.

        Invariant under test: on the first build, a non-user-edited
        agent-as-tool entry must have ``description == display_description``,
        exactly like regular tool components.
        """
        component = await self.component_setup(component_class, default_kwargs)

        await component._build_tools_metadata_input()

        metadata = component.tools_metadata
        assert metadata, "Agent-as-tool should produce at least one tool entry"
        for item in metadata:
            assert item["description"] == item["display_description"], (
                "Agent-as-tool description diverged from display_description on "
                f"first build (issue #9155): {item['description']!r} != {item['display_description']!r}"
            )

    async def test_should_propagate_description_change_when_agent_used_as_tool(self, component_class, default_kwargs):
        """Regression for GitHub issue #9155 (user-visible symptom).

        A change to the child agent's tool description must reach the parent
        agent's Actions panel on the next build, as long as the user did not
        manually customize it in the panel.
        """
        component = await self.component_setup(component_class, default_kwargs)

        await component._build_tools_metadata_input()
        first_description = component.tools_metadata[0]["description"]

        # Simulate the child agent's description changing (e.g. component.description),
        # then the parent re-reading the tool. The new value must propagate.
        component.description = "An updated agent description"
        await component._build_tools_metadata_input()
        second_description = component.tools_metadata[0]["description"]

        assert second_description != first_description, (
            "Description change on the child agent was not propagated to the "
            f"Actions panel (issue #9155): still {second_description!r}"
        )
        assert "An updated agent description" in second_description

    async def test_update_build_config_does_not_require_deprecated_agent_description(
        self, component_class, default_kwargs
    ):
        """Regression for PR #13151 review (P0).

        The deprecated ``agent_description`` input was removed from the agent
        template. The concrete ``AgentComponent`` must no longer list it in the
        ``update_build_config`` ``default_keys``, otherwise a model refresh
        raises ``ValueError: Missing required keys`` because the key is gone
        from the generated template.
        """
        from lfx.schema.dotdict import dotdict

        with patch("lfx.components.models_and_agents.agent.get_language_model_options") as mock_opts:
            mock_opts.return_value = [
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
            component = await self.component_setup(component_class, default_kwargs)
            frontend_node = component.to_frontend_node()
            build_config = frontend_node["data"]["node"]["template"]

            assert "agent_description" not in build_config, (
                "Deprecated agent_description must not be present in the agent template"
            )

            # Must not raise "Missing required keys in build_config".
            updated_config = await component.update_build_config(
                dotdict(build_config), mock_opts.return_value, field_name="model"
            )

        assert "agent_description" not in updated_config

    async def test_get_tools_does_not_call_removed_api(self, component_class, default_kwargs):
        """Regression for PR #13151 review (P0).

        The concrete ``AgentComponent._get_tools()`` used to call the removed
        ``get_tool_description()`` for a tool-description override. Building the
        agent-as-tool must not raise ``AttributeError`` and must succeed.
        """
        component = await self.component_setup(component_class, default_kwargs)

        tools = await component._get_tools()

        assert tools, "Agent-as-tool must still produce at least one tool"

    async def test_get_tool_description_backward_compat_shim(self, component_class, default_kwargs):
        """Regression for PR #13151 review (P1).

        Flows serialized with the pre-deprecation component code still call
        ``self.get_tool_description()``. The base class must keep this shim so
        those flows stay loadable: it returns the default when no
        ``agent_description`` is set, and the old value when an old serialized
        component still defines and sets it.
        """
        from lfx.base.agents.agent import DEFAULT_TOOLS_DESCRIPTION

        component = await self.component_setup(component_class, default_kwargs)

        # New components have no agent_description -> falls back to the default.
        assert component.get_tool_description() == DEFAULT_TOOLS_DESCRIPTION

        # Old serialized component code defines its own agent_description input
        # and sets it; the shim must surface that value unchanged.
        component.agent_description = "Legacy serialized description"
        assert component.get_tool_description() == "Legacy serialized description"


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

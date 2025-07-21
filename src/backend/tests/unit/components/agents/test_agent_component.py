import os
from typing import Any
from uuid import uuid4

import pytest
from langflow.base.models.anthropic_constants import ANTHROPIC_MODELS
from langflow.base.models.model_input_constants import (
    MODEL_PROVIDERS,
)
from langflow.base.models.openai_constants import (
    OPENAI_CHAT_MODEL_NAMES,
    OPENAI_REASONING_MODEL_NAMES,
)
from langflow.components.agents.agent import AgentComponent
from langflow.components.tools.calculator import CalculatorToolComponent
from langflow.custom import Component

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
        assert "Custom" in updated_config["agent_llm"]["options"]

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
        updated_config = await component.update_build_config(build_config, "Custom", "agent_llm")
        assert "agent_llm" in updated_config
        assert updated_config["agent_llm"]["value"] == "Custom"
        assert isinstance(updated_config["agent_llm"]["options"], list)
        assert len(updated_config["agent_llm"]["options"]) > 0
        assert all(provider in updated_config["agent_llm"]["options"] for provider in MODEL_PROVIDERS)
        assert "Custom" in updated_config["agent_llm"]["options"]
        assert updated_config["agent_llm"]["input_types"] == ["LanguageModel"]

        # Verify model_name field is cleared for Custom
        assert "model_name" not in updated_config

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

    async def test_json_mode_filtered_from_openai_inputs(self, component_class, default_kwargs):
        """Test that json_mode is filtered out from OpenAI inputs."""
        component = await self.component_setup(component_class, default_kwargs)

        # Check that json_mode is not in the agent's inputs
        input_names = [inp.name for inp in component.inputs if hasattr(inp, "name")]
        assert "json_mode" not in input_names

        # Verify other OpenAI inputs are still present
        assert "model_name" in input_names
        assert "api_key" in input_names
        assert "temperature" in input_names

    async def test_json_response_parsing_valid_json(self, component_class, default_kwargs):
        """Test that json_response correctly parses JSON from agent response."""
        component = await self.component_setup(component_class, default_kwargs)

        # Mock a response with valid JSON
        mock_result = type("MockResult", (), {"content": '{"name": "test", "value": 123}'})()
        component._agent_result = mock_result

        result = await component.json_response()

        from langflow.schema.data import Data

        assert isinstance(result, Data)
        assert result.data == {"name": "test", "value": 123}

    async def test_json_response_parsing_embedded_json(self, component_class, default_kwargs):
        """Test that json_response handles text containing JSON."""
        component = await self.component_setup(component_class, default_kwargs)

        # Mock a response with text containing JSON
        mock_result = type("MockResult", (), {"content": 'Here is the result: {"status": "success"} - done!'})()
        component._agent_result = mock_result

        result = await component.json_response()

        from langflow.schema.data import Data

        assert isinstance(result, Data)
        assert result.data == {"status": "success"}

    async def test_json_response_error_handling(self, component_class, default_kwargs):
        """Test that json_response handles completely non-JSON responses."""
        component = await self.component_setup(component_class, default_kwargs)

        # Mock a response with no JSON
        mock_result = type("MockResult", (), {"content": "This is just plain text with no JSON"})()
        component._agent_result = mock_result

        result = await component.json_response()

        from langflow.schema.data import Data

        assert isinstance(result, Data)
        assert "error" in result.data
        assert result.data["content"] == "This is just plain text with no JSON"

    async def test_model_building_without_json_mode(self, component_class, default_kwargs):
        """Test that model building works without json_mode attribute."""
        component = await self.component_setup(component_class, default_kwargs)
        component.agent_llm = "OpenAI"

        # Mock component for testing
        from unittest.mock import Mock

        mock_component = Mock()
        mock_component.set.return_value = mock_component

        # Should not raise AttributeError for missing json_mode
        result = component.set_component_params(mock_component)

        assert result is not None
        # Verify set was called (meaning no AttributeError occurred)
        mock_component.set.assert_called_once()

    async def test_shared_execution_between_outputs(self, component_class, default_kwargs):
        """Test that both outputs use the same agent execution."""
        component = await self.component_setup(component_class, default_kwargs)

        # Mock the message_response method
        from unittest.mock import AsyncMock

        mock_result = type("MockResult", (), {"content": '{"shared": "result"}'})()

        async def mock_message_response_side_effect():
            component._agent_result = mock_result
            return mock_result

        component.message_response = AsyncMock(side_effect=mock_message_response_side_effect)

        # Call json_response first
        json_result = await component.json_response()

        # message_response should have been called once
        component.message_response.assert_called_once()

        # Verify the result was stored and reused
        assert hasattr(component, "_agent_result")
        assert json_result.data == {"shared": "result"}

    async def test_agent_component_initialization(self, component_class, default_kwargs):
        """Test that Agent component initializes correctly with filtered inputs."""
        component = await self.component_setup(component_class, default_kwargs)

        # Should not raise any errors during initialization
        assert component.display_name == "Agent"
        assert component.name == "Agent"
        assert len(component.inputs) > 0
        assert len(component.outputs) == 2

    async def test_frontend_node_structure(self, component_class, default_kwargs):
        """Test that frontend node has correct structure with filtered inputs."""
        component = await self.component_setup(component_class, default_kwargs)

        frontend_node = component.to_frontend_node()
        build_config = frontend_node["data"]["node"]["template"]

        # Verify json_mode is not in build config
        assert "json_mode" not in build_config

        # Verify other expected fields are present
        assert "agent_llm" in build_config
        assert "system_prompt" in build_config
        assert "add_current_date_tool" in build_config


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
        api_key = os.getenv("OPENAI_API_KEY")
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
        api_key = os.getenv("OPENAI_API_KEY")
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

            except Exception as e:  # noqa: BLE001
                failed_models[model_name] = f"Exception occurred: {e!s}"

        assert not failed_models, "The following models failed the test:\n" + "\n".join(
            f"{model}: {error}" for model, error in failed_models.items()
        )

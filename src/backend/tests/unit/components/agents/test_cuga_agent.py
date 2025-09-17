import os
from typing import Any
from uuid import uuid4

import pytest
from langflow.custom import Component

from lfx.components.agents.cuga_agent import CugaComponent
from lfx.components.tools.calculator import CalculatorToolComponent
from tests.base import ComponentTestBaseWithClient, ComponentTestBaseWithoutClient
from tests.unit.mock_language_model import MockLanguageModel

# Load environment variables from .env file


class TestCugaComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return CugaComponent

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
            "_type": "Cuga",
            "add_current_date_tool": True,
            "agent_llm": MockLanguageModel(),
            "policies": "You are a helpful assistant.",
            "input_value": "",
            "n_messages": 100,
            "format_instructions": "You are an AI that extracts structured JSON objects from unstructured text.",
            "output_schema": [],
            "browser_enabled": False,
            "web_apps": "",
            "API": False,
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
        assert all(provider in updated_config["agent_llm"]["options"] for provider in ["OpenAI", "Custom"])
        assert "Custom" in updated_config["agent_llm"]["options"]

        # Verify model_name field is populated for OpenAI
        assert "model_name" in updated_config
        model_name_dict = updated_config["model_name"]
        assert isinstance(model_name_dict["options"], list)
        assert len(model_name_dict["options"]) > 0  # OpenAI should have available models
        assert "gpt-4o" in model_name_dict["options"]

        # Test Anthropic
        # TBD: Add test for Anthropic currently cuga does not support Anthropic

        # Test updating build config for Custom
        updated_config = await component.update_build_config(build_config, "Custom", "agent_llm")
        assert "agent_llm" in updated_config
        assert updated_config["agent_llm"]["value"] == "Custom"
        assert isinstance(updated_config["agent_llm"]["options"], list)
        assert len(updated_config["agent_llm"]["options"]) > 0
        assert all(provider in updated_config["agent_llm"]["options"] for provider in ["OpenAI", "Custom"])
        assert "Custom" in updated_config["agent_llm"]["options"]
        assert updated_config["agent_llm"]["input_types"] == ["LanguageModel"]

        # Verify model_name field is cleared for Custom
        assert "model_name" not in updated_config

    async def test_cuga_has_dual_outputs(self, component_class, default_kwargs):
        """Test that Cuga component has both Response and Structured Response outputs."""
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

        # Check that json_mode is not in the component's inputs
        input_names = [inp.name for inp in component.inputs if hasattr(inp, "name")]
        assert "json_mode" not in input_names

        # Verify other OpenAI inputs are still present
        assert "model_name" in input_names
        assert "api_key" in input_names
        assert "temperature" in input_names

    async def test_json_response_parsing_valid_json(self, component_class, default_kwargs):
        """Test that json_response correctly parses JSON from agent response."""
        component = await self.component_setup(component_class, default_kwargs)
        # Mock the get_agent_requirements method to avoid actual LLM calls
        from unittest.mock import AsyncMock

        component.get_agent_requirements = AsyncMock(return_value=(MockLanguageModel(), [], []))
        component.call_agent = AsyncMock(return_value='{"name": "test", "value": 123}')

        result = await component.json_response()

        from lfx.schema.data import Data

        assert isinstance(result, Data)
        assert result.data == {"name": "test", "value": 123}

    async def test_json_response_parsing_embedded_json(self, component_class, default_kwargs):
        """Test that json_response handles text containing JSON."""
        component = await self.component_setup(component_class, default_kwargs)
        # Mock the get_agent_requirements method to avoid actual LLM calls
        from unittest.mock import AsyncMock

        component.get_agent_requirements = AsyncMock(return_value=(MockLanguageModel(), [], []))
        component.call_agent = AsyncMock(return_value='Here is the result: {"status": "success"} - done!')

        result = await component.json_response()

        from lfx.schema.data import Data

        assert isinstance(result, Data)
        assert result.data == {"status": "success"}

    async def test_json_response_error_handling(self, component_class, default_kwargs):
        """Test that json_response handles completely non-JSON responses."""
        component = await self.component_setup(component_class, default_kwargs)
        # Mock the get_agent_requirements method to avoid actual LLM calls
        from unittest.mock import AsyncMock

        component.get_agent_requirements = AsyncMock(return_value=(MockLanguageModel(), [], []))
        component.call_agent = AsyncMock(return_value="This is just plain text with no JSON")

        result = await component.json_response()

        from lfx.schema.data import Data

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
        component.call_agent = AsyncMock(return_value='{"name": "John", "age": 25}')

        result = await component.json_response()

        from langflow.schema.data import Data

        assert isinstance(result, Data)
        assert result.data == {"name": "John", "age": 25}

    async def test_cuga_component_initialization(self, component_class, default_kwargs):
        """Test that Cuga component initializes correctly with filtered inputs."""
        component = await self.component_setup(component_class, default_kwargs)

        # Should not raise any errors during initialization
        assert component.display_name == "Cuga"
        assert component.name == "Cuga"
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
        assert "policies" in build_config
        assert "add_current_date_tool" in build_config
        assert "browser_enabled" in build_config
        assert "web_apps" in build_config
        assert "API" in build_config

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

    async def test_build_structured_output_base_without_schema(self, component_class, default_kwargs):
        """Test build_structured_output_base without schema validation."""
        component = await self.component_setup(component_class, default_kwargs)

        # Test with no output_schema
        content = '{"any": "data", "number": 123}'
        result = await component.build_structured_output_base(content)
        assert result == {"any": "data", "number": 123}

    async def test_build_structured_output_base_embedded_json(self, component_class, default_kwargs):
        """Test extraction of JSON from embedded text."""
        component = await self.component_setup(component_class, default_kwargs)

        content = 'Here is some text with {"embedded": "json"} inside it.'
        result = await component.build_structured_output_base(content)
        assert result == {"embedded": "json"}

    async def test_build_structured_output_base_no_json(self, component_class, default_kwargs):
        """Test handling of content with no JSON."""
        component = await self.component_setup(component_class, default_kwargs)

        content = "This is just plain text with no JSON at all."
        result = await component.build_structured_output_base(content)
        assert "error" in result
        assert result["content"] == content

    async def test_new_input_fields_present(self, component_class, default_kwargs):
        """Test that new input fields are present in the component."""
        component = await self.component_setup(component_class, default_kwargs)

        input_names = [inp.name for inp in component.inputs if hasattr(inp, "name")]

        # Test for new fields specific to Cuga
        assert "policies" in input_names
        assert "format_instructions" in input_names
        assert "output_schema" in input_names
        assert "n_messages" in input_names
        assert "browser_enabled" in input_names
        assert "web_apps" in input_names
        assert "API" in input_names

        # Verify default values
        assert hasattr(component, "policies")
        assert hasattr(component, "format_instructions")
        assert hasattr(component, "output_schema")
        assert hasattr(component, "n_messages")
        assert hasattr(component, "browser_enabled")
        assert hasattr(component, "web_apps")
        assert hasattr(component, "API")
        assert component.n_messages == 100
        assert component.browser_enabled is False
        assert component.API is False

    async def test_cuga_has_correct_outputs(self, component_class, default_kwargs):
        """Test that Cuga component has the correct output configuration."""
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

    async def test_memory_inputs_advanced_setting(self, component_class, default_kwargs):
        """Test that memory inputs are properly set to advanced."""
        # TBD: Add test for memory inputs

    async def test_browser_configuration(self, component_class, default_kwargs):
        """Test browser configuration options."""
        component = await self.component_setup(component_class, default_kwargs)

        # Test default browser settings
        assert component.browser_enabled is False
        assert component.web_apps == ""

        # Test setting browser enabled
        component.browser_enabled = True
        component.web_apps = "https://example.com"
        assert component.browser_enabled is True
        assert component.web_apps == "https://example.com"

    async def test_api_subagent_configuration(self, component_class, default_kwargs):
        """Test API sub-agent configuration."""
        component = await self.component_setup(component_class, default_kwargs)

        # Test default API setting
        assert component.API is False

        # Test setting API enabled
        component.API = True
        assert component.API is True


class TestCugaComponentWithClient(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return CugaComponent

    @pytest.fixture
    def file_names_mapping(self):
        return []

    @pytest.mark.api_key_required
    @pytest.mark.no_blockbuster
    async def test_cuga_component_with_calculator(self):
        # Now you can access the environment variables
        api_key = os.getenv("OPENAI_API_KEY")
        tools = [CalculatorToolComponent().build_tool()]  # Use the Calculator component as a tool
        input_value = "What is 2 + 2?"

        temperature = 0.1

        # Initialize the CugaComponent with mocked inputs
        cuga = CugaComponent(
            tools=tools,
            input_value=input_value,
            api_key=api_key,
            model_name="gpt-4o",
            agent_llm="OpenAI",
            temperature=temperature,
            _session_id=str(uuid4()),
        )

        response = await cuga.message_response()
        assert "4" in response.data.get("text")

    @pytest.mark.api_key_required
    @pytest.mark.no_blockbuster
    @pytest.mark.timeout(300)  # 5 minutes timeout for testing key OpenAI models
    async def test_cuga_component_with_all_openai_models(self):
        # Mock inputs
        api_key = os.getenv("OPENAI_API_KEY")
        input_value = "What is 2 + 2?"

        # Test only key OpenAI models to avoid timeout and complexity
        key_models = ["gpt-4o", "gpt-4o-mini"]
        failed_models = []

        for model_name in key_models:
            try:
                # Initialize the CugaComponent with mocked inputs
                tools = [CalculatorToolComponent().build_tool()]  # Use the Calculator component as a tool
                cuga = CugaComponent(
                    tools=tools,
                    input_value=input_value,
                    api_key=api_key,
                    model_name=model_name,
                    agent_llm="OpenAI",
                    _session_id=str(uuid4()),
                )

                response = await cuga.message_response()
                if "4" not in response.data.get("text"):
                    failed_models.append(model_name)
            except Exception as e:
                failed_models.append(f"{model_name} (error: {e!s})")

        assert not failed_models, f"The following models failed the test: {failed_models}"

    @pytest.mark.api_key_required
    @pytest.mark.no_blockbuster
    async def test_cuga_structured_response_with_schema(self):
        # TODO: Add test for structured response with schema
        pass

    @pytest.mark.api_key_required
    @pytest.mark.no_blockbuster
    async def test_cuga_with_policies(self):
        """Test Cuga with custom policies."""
        api_key = os.getenv("OPENAI_API_KEY")
        input_value = "What is 2 + 2?"
        policies = "## Answer\n\nYou must always respond with enthusiasm and use exclamation marks!"
        tools = [CalculatorToolComponent().build_tool()]
        cuga = CugaComponent(
            input_value=input_value,
            api_key=api_key,
            model_name="gpt-4o",
            agent_llm="OpenAI",
            policies=policies,
            tools=tools,
            _session_id=str(uuid4()),
        )

        response = await cuga.message_response()
        response_text = response.data.get("text", "")

        # Should contain the calculation result
        assert "4" in response_text
        assert "!" in response_text
        # Should show some enthusiasm (though this might be flaky depending on the model)
        # We'll just check that we got a response
        assert len(response_text) > 0

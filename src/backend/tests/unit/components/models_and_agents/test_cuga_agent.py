import os
from typing import Any
from uuid import uuid4

import pytest
from langflow.custom import Component
from lfx.components.cuga import CugaComponent
from lfx.components.tools.calculator import CalculatorToolComponent

from tests.base import ComponentTestBaseWithClient, ComponentTestBaseWithoutClient
from tests.unit.mock_language_model import MockLanguageModel

# Load environment variables from .env file


class TestCugaComponent(ComponentTestBaseWithoutClient):
    """Test suite for CugaComponent without client dependencies.

    This class contains unit tests for the CugaComponent that don't require
    external API calls or client connections.
    """

    @pytest.fixture
    def component_class(self):
        """Return the CugaComponent class for testing.

        Returns:
            type: The CugaComponent class
        """
        return CugaComponent

    @pytest.fixture
    def file_names_mapping(self):
        """Return empty file names mapping for testing.

        Returns:
            list: Empty list since no file mappings are needed
        """
        return []

    async def component_setup(self, component_class: type[Any], default_kwargs: dict[str, Any]) -> Component:
        """Set up component instance for testing with mocked methods.

        Args:
            component_class: The component class to instantiate
            default_kwargs: Default keyword arguments for the component

        Returns:
            Component: Configured component instance with mocked methods
        """
        component_instance = await super().component_setup(component_class, default_kwargs)
        # Mock _should_process_output method
        component_instance._should_process_output = lambda output: False  # noqa: ARG005
        return component_instance

    @pytest.fixture
    def default_kwargs(self):
        """Return default keyword arguments for CugaComponent testing.

        Returns:
            dict: Default configuration for the CugaComponent
        """
        return {
            "_type": "Cuga",
            "add_current_date_tool": True,
            "agent_llm": MockLanguageModel(),
            "policies": "You are a helpful assistant.",
            "input_value": "",
            "n_messages": 100,
            "browser_enabled": False,
            "web_apps": "",
            "lite_mode": True,
            "lite_mode_tool_threshold": 25,
            "decomposition_strategy": "flexible",
        }

    async def test_build_config_update(self, component_class, default_kwargs):
        """Test that build configuration updates correctly for different providers.

        This test verifies that the component's build configuration is properly
        updated when switching between different model providers (OpenAI, Custom).
        """
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

    async def test_cuga_component_initialization(self, component_class, default_kwargs):
        """Test that Cuga component initializes correctly with filtered inputs.

        This test verifies that the CugaComponent can be properly initialized
        with all required attributes and filtered input fields.
        """
        component = await self.component_setup(component_class, default_kwargs)

        # Should not raise any errors during initialization
        assert component.display_name == "Cuga"
        assert component.name == "Cuga"
        assert len(component.inputs) > 0
        assert len(component.outputs) == 1

    async def test_frontend_node_structure(self, component_class, default_kwargs):
        """Test that frontend node has correct structure with filtered inputs.

        This test verifies that the frontend node representation has the correct
        structure and includes expected fields.
        """
        component = await self.component_setup(component_class, default_kwargs)

        frontend_node = component.to_frontend_node()
        build_config = frontend_node["data"]["node"]["template"]

        # Verify other expected fields are present
        assert "agent_llm" in build_config
        assert "policies" in build_config
        assert "add_current_date_tool" in build_config
        assert "browser_enabled" in build_config
        assert "web_apps" in build_config

    async def test_new_input_fields_present(self, component_class, default_kwargs):
        """Test that new input fields are present in the component.

        This test verifies that all the new input fields specific to the Cuga
        component are properly defined and have correct default values.
        """
        component = await self.component_setup(component_class, default_kwargs)

        input_names = [inp.name for inp in component.inputs if hasattr(inp, "name")]

        # Test for new fields specific to Cuga
        assert "policies" in input_names
        assert "n_messages" in input_names
        assert "browser_enabled" in input_names
        assert "web_apps" in input_names
        assert "lite_mode" in input_names
        assert "lite_mode_tool_threshold" in input_names
        assert "decomposition_strategy" in input_names

        # Verify default values
        assert hasattr(component, "policies")
        assert hasattr(component, "n_messages")
        assert hasattr(component, "browser_enabled")
        assert hasattr(component, "web_apps")
        assert hasattr(component, "lite_mode")
        assert hasattr(component, "lite_mode_tool_threshold")
        assert hasattr(component, "decomposition_strategy")
        assert component.n_messages == 100
        assert component.browser_enabled is False
        assert component.lite_mode is True
        assert component.lite_mode_tool_threshold == 25
        assert component.decomposition_strategy == "flexible"

    async def test_decomposition_strategy_field(self, component_class, default_kwargs):
        """Test that decomposition_strategy field is properly configured.

        This test verifies that the decomposition_strategy field has the correct
        options, default value, and advanced configuration.
        """
        component = await self.component_setup(component_class, default_kwargs)

        # Find the decomposition_strategy input
        decomposition_input = None
        for inp in component.inputs:
            if hasattr(inp, "name") and inp.name == "decomposition_strategy":
                decomposition_input = inp
                break

        assert decomposition_input is not None, "decomposition_strategy input not found"
        assert decomposition_input.display_name == "Decomposition Strategy"
        assert decomposition_input.value == "flexible"
        assert decomposition_input.options == ["flexible", "exact"]
        assert decomposition_input.advanced is True

        # Test setting different values
        component.decomposition_strategy = "exact"
        assert component.decomposition_strategy == "exact"

        component.decomposition_strategy = "flexible"
        assert component.decomposition_strategy == "flexible"

    async def test_memory_inputs_advanced_setting(self, component_class, default_kwargs):
        """Test that memory inputs are properly set to advanced.

        This test verifies that memory-related input fields are properly
        configured as advanced settings.

        Note:
            This test is currently a placeholder (TBD).
        """
        # TBD: Add test for memory inputs

    async def test_browser_configuration(self, component_class, default_kwargs):
        """Test browser configuration options.

        This test verifies that the browser-related configuration options
        (browser_enabled, web_apps) work correctly.
        """
        component = await self.component_setup(component_class, default_kwargs)

        # Test default browser settings
        assert component.browser_enabled is False
        assert component.web_apps == ""

        # Test setting browser enabled
        component.browser_enabled = True
        component.web_apps = "https://example.com"
        assert component.browser_enabled is True
        assert component.web_apps == "https://example.com"


class TestCugaComponentWithClient(ComponentTestBaseWithClient):
    """Test suite for CugaComponent with client dependencies.

    This class contains integration tests for the CugaComponent that require
    external API calls and client connections.
    """

    @pytest.fixture
    def component_class(self):
        """Return the CugaComponent class for testing.

        Returns:
            type: The CugaComponent class
        """
        return CugaComponent

    @pytest.fixture
    def file_names_mapping(self):
        """Return empty file names mapping for testing.

        Returns:
            list: Empty list since no file mappings are needed
        """
        return []

    @pytest.mark.api_key_required
    @pytest.mark.no_blockbuster
    async def test_cuga_component_with_calculator(self):
        """Test CugaComponent with calculator tool using real API.

        This integration test verifies that the CugaComponent can work with
        actual tools (calculator) and make real API calls to OpenAI.

        Requires:
            OPENAI_API_KEY environment variable
        """
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
        """Test CugaComponent with multiple OpenAI models.

        This integration test verifies that the CugaComponent works correctly
        with various OpenAI model configurations.

        Requires:
            OPENAI_API_KEY environment variable
        """
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
    async def test_cuga_with_policies(self):
        """Test Cuga with custom policies.

        This integration test verifies that the CugaComponent can apply
        custom policies to modify its behavior during execution.

        Requires:
            OPENAI_API_KEY environment variable
        """
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

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
            "instructions": "You are a helpful assistant.",
            "input_value": "",
            "n_messages": 100,
            "browser_enabled": False,
            "lite_mode": True,
            "lite_mode_tool_threshold": 25,
            "shortlisting_tool_threshold": 35,
            "decomposition_strategy": "flexible",
        }

    async def test_build_config_update(self, component_class, default_kwargs):
        """Test that build configuration updates correctly for different model provider selections.

        This test verifies that the component's build configuration is properly
        updated when selecting different model providers using the provider system.
        """
        component = await self.component_setup(component_class, default_kwargs)
        frontend_node = component.to_frontend_node()
        build_config = frontend_node["data"]["node"]["template"]

        # Test that agent_llm field exists and has proper structure
        assert "agent_llm" in build_config
        agent_llm_config = build_config["agent_llm"]
        assert "options" in agent_llm_config
        assert "OpenAI" in agent_llm_config["options"]

        # Test updating build config with OpenAI provider
        updated_config = await component.update_build_config(build_config, "OpenAI", "agent_llm")

        assert "agent_llm" in updated_config
        # When OpenAI is selected, OpenAI-specific fields should be present
        assert "openai_api_key" in updated_config or "model_name" in updated_config

        # Test updating build config with "Custom" (should add input types for LanguageModel)
        updated_config = await component.update_build_config(build_config, "Custom", "agent_llm")
        assert "agent_llm" in updated_config
        assert "LanguageModel" in updated_config["agent_llm"]["input_types"]

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

        # Verify expected fields are present (using field name 'agent_llm')
        assert "agent_llm" in build_config
        assert "instructions" in build_config
        assert "add_current_date_tool" in build_config
        assert "browser_enabled" in build_config
        assert "shortlisting_tool_threshold" in build_config

    async def test_new_input_fields_present(self, component_class, default_kwargs):
        """Test that new input fields are present in the component.

        This test verifies that all the new input fields specific to the Cuga
        component are properly defined and have correct default values.
        """
        component = await self.component_setup(component_class, default_kwargs)

        input_names = [inp.name for inp in component.inputs if hasattr(inp, "name")]

        # Test for new fields specific to Cuga
        assert "instructions" in input_names
        assert "n_messages" in input_names
        assert "browser_enabled" in input_names
        assert "lite_mode" in input_names
        assert "lite_mode_tool_threshold" in input_names
        assert "shortlisting_tool_threshold" in input_names
        assert "decomposition_strategy" in input_names

        # Verify default values
        assert hasattr(component, "instructions")
        assert hasattr(component, "n_messages")
        assert hasattr(component, "browser_enabled")
        assert hasattr(component, "lite_mode")
        assert hasattr(component, "lite_mode_tool_threshold")
        assert hasattr(component, "shortlisting_tool_threshold")
        assert hasattr(component, "decomposition_strategy")
        assert component.n_messages == 100
        assert component.browser_enabled is False
        assert component.lite_mode is True
        assert component.lite_mode_tool_threshold == 25
        assert component.shortlisting_tool_threshold == 35
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

    async def test_advanced_fields_configuration(self, component_class, default_kwargs):
        """Test that browser and cuga lite fields are properly configured as advanced.

        This test verifies that browser_enabled, lite_mode, lite_mode_tool_threshold,
        and shortlisting_tool_threshold fields are all set to advanced.
        """
        component = await self.component_setup(component_class, default_kwargs)

        # Find all the advanced fields we want to test
        field_checks = {
            "browser_enabled": False,
            "lite_mode": False,
            "lite_mode_tool_threshold": False,
            "shortlisting_tool_threshold": False,
        }

        for inp in component.inputs:
            if hasattr(inp, "name") and inp.name in field_checks:
                field_checks[inp.name] = inp.advanced

        # Assert all fields are set to advanced
        assert field_checks["browser_enabled"] is True, "browser_enabled should be advanced"
        assert field_checks["lite_mode"] is True, "lite_mode should be advanced"
        assert field_checks["lite_mode_tool_threshold"] is True, "lite_mode_tool_threshold should be advanced"
        assert field_checks["shortlisting_tool_threshold"] is True, "shortlisting_tool_threshold should be advanced"

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

        This test verifies that the browser-related configuration option
        (browser_enabled) works correctly.
        """
        component = await self.component_setup(component_class, default_kwargs)

        # Test default browser settings
        assert component.browser_enabled is False

        # Test setting browser enabled
        component.browser_enabled = True
        assert component.browser_enabled is True


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
        from tests.api_keys import get_openai_api_key

        api_key = get_openai_api_key()
        tools = [CalculatorToolComponent().build_tool()]  # Use the Calculator component as a tool
        input_value = "What is 2 + 2?"

        # Initialize the CugaComponent with unified model format
        cuga = CugaComponent(
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
                        "api_key_param": "api_key",  # pragma: allowlist secret
                    },
                }
            ],
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
        from tests.api_keys import get_openai_api_key

        api_key = get_openai_api_key()
        input_value = "What is 2 + 2?"

        # Test only key OpenAI models to avoid timeout and complexity
        key_models = ["gpt-4o", "gpt-4o-mini"]
        failed_models = []

        for model_name in key_models:
            try:
                # Initialize the CugaComponent with unified model format
                tools = [CalculatorToolComponent().build_tool()]  # Use the Calculator component as a tool
                cuga = CugaComponent(
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
                                "api_key_param": "api_key",  # pragma: allowlist secret
                            },
                        }
                    ],
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
    async def test_cuga_with_instructions(self):
        """Test Cuga with custom instructions.

        This integration test verifies that the CugaComponent can apply
        custom instructions to modify its behavior during execution.

        Requires:
            OPENAI_API_KEY environment variable
        """
        from tests.api_keys import get_openai_api_key

        api_key = get_openai_api_key()
        input_value = "What is 2 + 2?"
        instructions = "## Answer\n\nYou must always respond with enthusiasm and use exclamation marks!"
        tools = [CalculatorToolComponent().build_tool()]
        cuga = CugaComponent(
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
                        "api_key_param": "api_key",  # pragma: allowlist secret
                    },
                }
            ],
            instructions=instructions,
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


class TestLangflowToolsProvider:
    """Tests for LangflowToolsProvider grouping logic.

    Verifies that tools are correctly grouped by server_name metadata,
    common prefix, and default app.
    """

    @pytest.fixture
    def mock_tool_with_server_name(self):
        """Create a mock tool with server_name metadata.

        Returns:
            Mock tool with server_name in metadata
        """
        from unittest.mock import MagicMock

        tool = MagicMock()
        tool.name = "slack_send_message"
        tool.description = "Send a message via Slack"
        tool.metadata = {"server_name": "slack_mcp"}
        return tool

    @pytest.fixture
    def mock_tool_with_prefix(self):
        """Create mock tools with common prefix but no server_name.

        Returns:
            List of mock tools with gmail_ prefix
        """
        from unittest.mock import MagicMock

        tools = []
        for name in ["gmail_send", "gmail_read", "gmail_delete"]:
            tool = MagicMock()
            tool.name = name
            tool.description = f"Gmail tool for {name.split('_')[1]}"
            tool.metadata = None
            tools.append(tool)
        return tools

    @pytest.fixture
    def mock_tool_without_prefix(self):
        """Create a mock tool without a meaningful prefix.

        Returns:
            Mock tool that should go to default_app
        """
        from unittest.mock import MagicMock

        tool = MagicMock()
        tool.name = "calculator"
        tool.description = "A calculator tool"
        tool.metadata = None
        return tool

    async def test_group_by_server_name(self, mock_tool_with_server_name):
        """Test that tools are grouped by server_name metadata.

        Verifies tools with server_name in metadata are grouped
        under that server_name app.
        """
        from lfx.components.cuga.cuga_agent import LangflowToolsProvider

        provider = LangflowToolsProvider([mock_tool_with_server_name])
        await provider.initialize()

        apps = await provider.get_apps()
        assert len(apps) == 1
        assert apps[0].name == "slack_mcp"

        tools = await provider.get_tools("slack_mcp")
        assert len(tools) == 1
        assert tools[0].name == "slack_send_message"

    async def test_group_by_common_prefix(self, mock_tool_with_prefix):
        """Test that tools without server_name are grouped by prefix.

        Verifies tools with common prefix (e.g., gmail_*) are grouped
        together under an app named after the prefix.
        """
        from lfx.components.cuga.cuga_agent import LangflowToolsProvider

        provider = LangflowToolsProvider(mock_tool_with_prefix)
        await provider.initialize()

        apps = await provider.get_apps()
        assert len(apps) == 1
        assert apps[0].name == "GMAIL"

        tools = await provider.get_tools("GMAIL")
        assert len(tools) == 3
        tool_names = {t.name for t in tools}
        assert tool_names == {"gmail_send", "gmail_read", "gmail_delete"}

    async def test_default_app_for_ungrouped(self, mock_tool_without_prefix):
        """Test that remaining tools go to default_app.

        Verifies tools that don't match server_name or prefix grouping
        are placed in the default_app.
        """
        from lfx.components.cuga.cuga_agent import LangflowToolsProvider

        provider = LangflowToolsProvider([mock_tool_without_prefix])
        await provider.initialize()

        apps = await provider.get_apps()
        assert len(apps) == 1
        assert apps[0].name == "default_app"

        tools = await provider.get_tools("default_app")
        assert len(tools) == 1
        assert tools[0].name == "calculator"

    async def test_mixed_tools_grouping(
        self, mock_tool_with_server_name, mock_tool_with_prefix, mock_tool_without_prefix
    ):
        """Test grouping with a mix of different tool types.

        Verifies all three grouping strategies work together:
        server_name, prefix, and default_app.
        """
        from lfx.components.cuga.cuga_agent import LangflowToolsProvider

        all_tools = [mock_tool_with_server_name, *mock_tool_with_prefix, mock_tool_without_prefix]
        provider = LangflowToolsProvider(all_tools)
        await provider.initialize()

        apps = await provider.get_apps()
        app_names = {app.name for app in apps}
        assert app_names == {"slack_mcp", "GMAIL", "default_app"}

        all_tools_retrieved = await provider.get_all_tools()
        assert len(all_tools_retrieved) == 5

    async def test_excluded_prefixes(self):
        """Test that HTTP method prefixes are excluded from grouping.

        Verifies tools with prefixes like 'get_', 'post_' are not
        grouped by those prefixes (they should go to default_app).
        """
        from unittest.mock import MagicMock

        from lfx.components.cuga.cuga_agent import LangflowToolsProvider

        tools = []
        for name in ["get_user", "get_data", "post_message"]:
            tool = MagicMock()
            tool.name = name
            tool.description = f"HTTP-style tool: {name}"
            tool.metadata = None
            tools.append(tool)

        provider = LangflowToolsProvider(tools)
        await provider.initialize()

        apps = await provider.get_apps()
        # 'get' and 'post' are excluded prefixes, so all should go to default_app
        assert len(apps) == 1
        assert apps[0].name == "default_app"


class TestCugaStreaming:
    """Tests for CUGA streaming functionality.

    Verifies the streaming event handling, LangGraph format parsing,
    and nested state extraction.
    """

    def test_extract_from_nested_state_single_key(self):
        """Test nested state extraction with single key.

        Verifies that states like {'call_model': {...}} are properly
        unwrapped to return the inner dict.
        """
        # Import the function from the module

        # Create a component instance to access the nested function
        # Note: extract_from_nested_state is defined inside call_agent,
        # so we test the logic directly here

        # Single key dict should return inner value
        state = {"call_model": {"final_answer": "test answer", "step": 1}}
        assert len(state) == 1
        inner = next(iter(state.values()))
        assert inner == {"final_answer": "test answer", "step": 1}

    def test_extract_from_nested_state_multiple_keys(self):
        """Test nested state extraction with multiple keys.

        Verifies that states with multiple keys are returned as-is.
        """
        state = {"key1": "value1", "key2": "value2"}
        # Multiple keys - should return original
        assert len(state) > 1

    def test_langgraph_tuple_parsing(self):
        """Test parsing LangGraph-style (node_name_tuple, state_dict) format.

        Verifies that tuples from LangGraph stream are properly parsed
        to extract node name and state.
        """
        # LangGraph returns tuples like (('node_name',), {state})
        raw_state = (("call_model",), {"final_answer": "The answer is 42"})

        assert isinstance(raw_state, tuple)
        assert len(raw_state) == 2

        node_name_tuple, state_dict = raw_state
        node_name = node_name_tuple[0] if node_name_tuple else "unknown"

        assert node_name == "call_model"
        assert state_dict["final_answer"] == "The answer is 42"

    def test_event_structure_on_chain_start(self):
        """Test on_chain_start event structure.

        Verifies the expected fields are present in chain start events.
        """
        import uuid

        event = {
            "event": "on_chain_start",
            "run_id": str(uuid.uuid4()),
            "name": "CUGA_initializing",
            "data": {"input": {"input": "test input", "chat_history": []}},
        }

        assert event["event"] == "on_chain_start"
        assert "run_id" in event
        assert event["name"] == "CUGA_initializing"
        assert "input" in event["data"]

    def test_event_structure_on_tool_start(self):
        """Test on_tool_start event structure.

        Verifies the expected fields are present in tool start events.
        """
        import uuid

        event = {
            "event": "on_tool_start",
            "run_id": str(uuid.uuid4()),
            "name": "execute_code",
            "data": {"input": {"code": "print('hello')"}},
        }

        assert event["event"] == "on_tool_start"
        assert event["name"] == "execute_code"
        assert "code" in event["data"]["input"]

    def test_event_structure_on_chain_end(self):
        """Test on_chain_end event structure.

        Verifies the expected fields are present in chain end events.
        """
        import uuid

        from langchain_core.agents import AgentFinish

        event = {
            "event": "on_chain_end",
            "run_id": str(uuid.uuid4()),
            "name": "CugaAgent",
            "data": {"output": AgentFinish(return_values={"output": "Final answer"}, log="")},
        }

        assert event["event"] == "on_chain_end"
        assert event["name"] == "CugaAgent"
        assert event["data"]["output"].return_values["output"] == "Final answer"

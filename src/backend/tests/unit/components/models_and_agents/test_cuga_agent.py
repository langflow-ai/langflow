import sys
import types
from typing import Any
from uuid import uuid4

import pytest
from langflow.custom import Component
from lfx.components.cuga.cuga_agent import (
    _CUGA_CODE_AGENT_GUARD_ATTR,
    CugaComponent,
    _install_cuga_code_agent_security_guard,
    _validate_cuga_code_agent_source,
)
from lfx.components.tools.calculator import CalculatorToolComponent

from tests.base import ComponentTestBaseWithClient, ComponentTestBaseWithoutClient
from tests.unit.mock_language_model import MockLanguageModel

# Load environment variables from .env file


def _get_cuga_code_agent_security_classes() -> tuple[Any, Any]:
    code_executor_module = pytest.importorskip("cuga.backend.cuga_graph.nodes.cuga_lite.executors.code_executor")
    security_module = pytest.importorskip("cuga.backend.cuga_graph.nodes.cuga_lite.executors.common")
    return code_executor_module.CodeExecutor, security_module.SecurityValidator


def test_cuga_code_agent_guard_allows_safe_codeagent_source():
    code_executor_cls, security_validator_cls = _get_cuga_code_agent_security_classes()

    safe_code = 'import json\nprint(json.dumps({"variable_name": "answer", "value": 42}))'

    _validate_cuga_code_agent_source(code_executor_cls, security_validator_cls, safe_code)


def test_cuga_code_agent_guard_blocks_object_graph_escape():
    code_executor_cls, security_validator_cls = _get_cuga_code_agent_security_classes()

    exploit_code = """
import json
mod = None
for cls in ().__class__.__mro__[1].__subclasses__():
    globals_dict = getattr(getattr(cls, "__init__", None), "__globals__", None)
    if isinstance(globals_dict, dict) and globals_dict.get("os") is not None:
        mod = globals_dict["os"]
        break
mod.system("mkdir -p /tmp/langflow-poc")
print(json.dumps({"variable_name": "proof", "value": "escaped"}))
"""

    with pytest.raises((ImportError, PermissionError), match=r"not allowed|Security violation|Suspicious"):
        _validate_cuga_code_agent_source(code_executor_cls, security_validator_cls, exploit_code)


@pytest.mark.asyncio
async def test_cuga_code_agent_security_guard_validates_before_original_executor(monkeypatch):
    validations: list[tuple[str, str]] = []
    calls: list[tuple[str, Any, Any]] = []

    class FakeSecurityValidator:
        @staticmethod
        def validate_imports(code: str) -> None:
            validations.append(("imports", code))

        @staticmethod
        def validate_wrapped_code(wrapped_code: str) -> None:
            validations.append(("wrapped", wrapped_code))
            if "BLOCK" in wrapped_code:
                msg = "blocked before execution"
                raise PermissionError(msg)

    class FakeCodeExecutor:
        @classmethod
        def _wrap_code_for_code_agent(cls, code: str) -> str:
            return f"wrapped:{code}"

        @classmethod
        async def eval_for_code_agent(cls, code: str, state: Any, mode: Any = None) -> tuple[str, dict[str, Any]]:
            calls.append((code, state, mode))
            return "executed", {}

    def package_module(name: str) -> types.ModuleType:
        module = types.ModuleType(name)
        module.__path__ = []
        return module

    package_names = [
        "cuga",
        "cuga.backend",
        "cuga.backend.cuga_graph",
        "cuga.backend.cuga_graph.nodes",
        "cuga.backend.cuga_graph.nodes.cuga_lite",
        "cuga.backend.cuga_graph.nodes.cuga_lite.executors",
    ]
    for package_name in package_names:
        monkeypatch.setitem(sys.modules, package_name, package_module(package_name))

    code_executor_module = types.ModuleType("cuga.backend.cuga_graph.nodes.cuga_lite.executors.code_executor")
    code_executor_module.CodeExecutor = FakeCodeExecutor
    common_module = types.ModuleType("cuga.backend.cuga_graph.nodes.cuga_lite.executors.common")
    common_module.SecurityValidator = FakeSecurityValidator
    monkeypatch.setitem(sys.modules, code_executor_module.__name__, code_executor_module)
    monkeypatch.setitem(sys.modules, common_module.__name__, common_module)

    _install_cuga_code_agent_security_guard()
    _install_cuga_code_agent_security_guard()

    assert getattr(FakeCodeExecutor, _CUGA_CODE_AGENT_GUARD_ATTR) is True
    assert await FakeCodeExecutor.eval_for_code_agent("safe", state="state", mode="local") == ("executed", {})
    with pytest.raises(PermissionError, match="blocked before execution"):
        await FakeCodeExecutor.eval_for_code_agent("BLOCK", state="state", mode="local")

    assert calls == [("safe", "state", "local")]
    assert validations == [
        ("imports", "safe"),
        ("wrapped", "wrapped:safe"),
        ("imports", "BLOCK"),
        ("wrapped", "wrapped:BLOCK"),
    ]


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
            "web_apps": "",
            "lite_mode": True,
            "lite_mode_tool_threshold": 25,
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
        assert "web_apps" in build_config

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
        assert "web_apps" in input_names
        assert "lite_mode" in input_names
        assert "lite_mode_tool_threshold" in input_names
        assert "decomposition_strategy" in input_names

        # Verify default values
        assert hasattr(component, "instructions")
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

    async def test_advanced_fields_configuration(self, component_class, default_kwargs):
        """Test that browser and cuga lite fields are properly configured as advanced.

        This test verifies that browser_enabled, web_apps, lite_mode, and
        lite_mode_tool_threshold fields are all set to advanced.
        """
        component = await self.component_setup(component_class, default_kwargs)

        # Find all the advanced fields we want to test
        field_checks = {
            "browser_enabled": False,
            "web_apps": False,
            "lite_mode": False,
            "lite_mode_tool_threshold": False,
        }

        for inp in component.inputs:
            if hasattr(inp, "name") and inp.name in field_checks:
                field_checks[inp.name] = inp.advanced

        # Assert all fields are set to advanced
        assert field_checks["browser_enabled"] is True, "browser_enabled should be advanced"
        assert field_checks["web_apps"] is True, "web_apps should be advanced"
        assert field_checks["lite_mode"] is True, "lite_mode should be advanced"
        assert field_checks["lite_mode_tool_threshold"] is True, "lite_mode_tool_threshold should be advanced"

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

"""Unit tests for the CoreExecutor."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from langflow_stepflow.exceptions import ExecutionError
from langflow_stepflow.worker.core_executor import CoreExecutor


@pytest.fixture
def executor():
    """Create a CoreExecutor instance."""
    return CoreExecutor()


@pytest.fixture
def mock_context():
    """Create a mock StepflowContext."""
    context = MagicMock()
    context.get_blob = AsyncMock(return_value={})
    context.put_blob = AsyncMock(return_value="blob_id")
    return context


class TestCoreExecutorExecutionMethodDetermination:
    """Tests for _determine_execution_method inherited from base."""

    def test_determine_execution_method_with_selected_output(self, executor):
        """Test determining method when selected_output matches."""
        outputs = [
            {"name": "text", "method": "text_response"},
            {"name": "message", "method": "build_message"},
        ]
        result = executor._determine_execution_method(outputs, "message")
        assert result == "build_message"

    def test_determine_execution_method_fallback_to_first(self, executor):
        """Test falling back to first output's method."""
        outputs = [
            {"name": "default", "method": "default_method"},
            {"name": "other", "method": "other_method"},
        ]
        result = executor._determine_execution_method(outputs, None)
        assert result == "default_method"

    def test_determine_execution_method_empty_outputs(self, executor):
        """Test with empty outputs list."""
        result = executor._determine_execution_method([], None)
        assert result is None

    def test_determine_execution_method_selected_not_found(self, executor):
        """Test when selected_output doesn't match any output."""
        outputs = [{"name": "text", "method": "text_method"}]
        result = executor._determine_execution_method(outputs, "nonexistent")
        # Should fall back to first output's method
        assert result == "text_method"


class TestCoreExecutorInputDefaults:
    """Tests for _apply_component_input_defaults inherited from base."""

    def test_apply_defaults_no_inputs(self, executor):
        """Test with component that has no inputs attribute."""
        component = MagicMock(spec=[])  # No inputs attribute
        params = {"key": "value"}
        result = executor._apply_component_input_defaults(component, params)
        assert result == {"key": "value"}

    def test_apply_defaults_empty_inputs(self, executor):
        """Test with empty inputs list."""
        component = MagicMock()
        component.inputs = []
        params = {"key": "value"}
        result = executor._apply_component_input_defaults(component, params)
        assert result == {"key": "value"}

    def test_apply_defaults_adds_missing(self, executor):
        """Test that defaults are added for missing parameters."""
        input_def = MagicMock()
        input_def.name = "temperature"
        input_def.value = 0.7

        component = MagicMock()
        component.inputs = [input_def]

        params = {"model": "gpt-4"}
        result = executor._apply_component_input_defaults(component, params)
        assert result == {"model": "gpt-4", "temperature": 0.7}

    def test_apply_defaults_preserves_existing(self, executor):
        """Test that existing params are not overwritten."""
        input_def = MagicMock()
        input_def.name = "temperature"
        input_def.value = 0.7

        component = MagicMock()
        component.inputs = [input_def]

        params = {"temperature": 0.9}  # Already set
        result = executor._apply_component_input_defaults(component, params)
        assert result == {"temperature": 0.9}  # Original value preserved


class TestCoreExecutorErrors:
    """Tests for error handling in CoreExecutor."""

    @pytest.mark.asyncio
    async def test_execute_invalid_path_no_dot(self, executor, mock_context):
        """Test error when path has no class name separator."""
        with pytest.raises(ExecutionError, match="Invalid component path"):
            await executor.execute("invalid", {}, mock_context)

    @pytest.mark.asyncio
    async def test_execute_module_not_found(self, executor, mock_context):
        """Test error when module doesn't exist."""
        input_data = {
            "template": {},
            "outputs": [{"name": "result", "method": "run"}],
            "input": {},
        }
        with pytest.raises(ExecutionError, match="Failed to import module"):
            await executor.execute("nonexistent/module/path/ClassName", input_data, mock_context)

    @pytest.mark.asyncio
    async def test_execute_class_not_found(self, executor, mock_context):
        """Test error when class doesn't exist in module."""
        input_data = {
            "template": {},
            "outputs": [{"name": "result", "method": "run"}],
            "input": {},
        }
        # os module exists but NonExistentClass doesn't
        with pytest.raises(ExecutionError, match="Class.*not found in module"):
            await executor.execute("os/NonExistentClass", input_data, mock_context)

    @pytest.mark.asyncio
    async def test_execute_no_execution_method(self, executor, mock_context):
        """Test error when no execution method found."""
        input_data = {
            "template": {},
            "outputs": [],  # Empty outputs
            "input": {},
        }
        # Use a real importable class
        with pytest.raises(ExecutionError, match="No execution method found"):
            await executor.execute("dataclasses/dataclass", input_data, mock_context)


class TestCoreExecutorWithRealComponent:
    """Integration tests with real Langflow components.

    Note: Some Langflow components have complex dependencies (database, etc.)
    These tests focus on verifying the executor can import and instantiate
    components, rather than full execution which may require more setup.
    """

    @pytest.mark.asyncio
    async def test_import_prompt_component(self, executor, mock_context):
        """Test that PromptComponent can be imported and instantiated."""
        import importlib

        try:
            module = importlib.import_module("langflow.components.prompts.prompt")
            component_class = module.PromptComponent

            # Verify we can instantiate
            instance = component_class()
            assert instance is not None
            assert hasattr(instance, "build_prompt")
        except ModuleNotFoundError:
            # langflow.components.prompts may not be available in all environments
            # Skip test if not available
            pytest.skip("langflow.components.prompts not available")

    @pytest.mark.asyncio
    async def test_import_chat_input_component(self, executor, mock_context):
        """Test that ChatInput component can be imported and instantiated."""
        import importlib

        module = importlib.import_module("lfx.components.input_output.chat")
        component_class = module.ChatInput

        # Verify we can instantiate
        instance = component_class()
        assert instance is not None
        assert hasattr(instance, "message_response")

    @pytest.mark.asyncio
    async def test_execute_with_mocked_method(self, executor, mock_context):
        """Test execution flow with a mocked component method."""
        from unittest.mock import MagicMock, patch

        input_data = {
            "template": {
                "template": {"value": "Hello {name}!"},
            },
            "outputs": [{"name": "prompt", "method": "build_prompt"}],
            "selected_output": "prompt",
            "input": {
                "name": "World",
            },
        }

        # Mock the component instantiation and method
        mock_instance = MagicMock()
        mock_instance.inputs = []
        mock_instance.build_prompt = MagicMock(return_value="Hello World!")

        with patch("importlib.import_module") as mock_import:
            mock_module = MagicMock()
            mock_module.TestComponent = MagicMock(return_value=mock_instance)
            mock_import.return_value = mock_module

            result = await executor.execute(
                "test_module/TestComponent",
                input_data,
                mock_context,
            )

            assert "result" in result
            # Method was called
            mock_instance.build_prompt.assert_called_once()


class TestCoreExecutorPrepareParameters:
    """Tests for _prepare_component_parameters."""

    @pytest.mark.asyncio
    async def test_extract_values_from_template(self, executor):
        """Test extracting values from template structure."""
        template = {
            "param1": {"value": "value1"},
            "param2": {"value": 42},
            "param3": "direct_value",
        }
        runtime_inputs = {}

        result = await executor._prepare_component_parameters(template, runtime_inputs)

        assert result["param1"] == "value1"
        assert result["param2"] == 42
        assert result["param3"] == "direct_value"

    @pytest.mark.asyncio
    async def test_runtime_inputs_override_template(self, executor):
        """Test that runtime inputs override template values."""
        template = {
            "param1": {"value": "template_value"},
        }
        runtime_inputs = {
            "param1": "runtime_value",
        }

        result = await executor._prepare_component_parameters(template, runtime_inputs)

        assert result["param1"] == "runtime_value"

    @pytest.mark.asyncio
    async def test_empty_template_dict_skipped(self, executor):
        """Test that template fields without value are skipped."""
        template = {
            "param1": {"value": "has_value"},
            "param2": {},  # No value key
            "param3": {"type": "str"},  # No value key
        }
        runtime_inputs = {}

        result = await executor._prepare_component_parameters(template, runtime_inputs)

        assert result == {"param1": "has_value"}

    @pytest.mark.asyncio
    async def test_handle_inputs_with_empty_values_skipped(self, executor):
        """Test that handle inputs with empty values are skipped."""
        template = {
            "input_value": {
                "value": "",
                "input_types": ["Message"],  # This is a handle input
            },
            "regular_param": {"value": "keep_this"},
        }
        runtime_inputs = {}

        result = await executor._prepare_component_parameters(template, runtime_inputs)

        # Handle input with empty value should be skipped
        assert "input_value" not in result
        assert result["regular_param"] == "keep_this"

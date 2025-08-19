import pytest
from langflow.components.logic.notify import NotifyComponent
from langflow.schema.data import Data


class TestNotifyComponent:
    """Test cases for NotifyComponent."""

    @pytest.fixture
    def component(self):
        """Create a NotifyComponent instance for testing."""
        return NotifyComponent()

    def test_component_initialization(self, component):
        """Test proper initialization of NotifyComponent."""
        assert component.display_name == "Notify"
        assert component.description == "A component to generate a notification to Get Notified component."
        assert component.icon == "Notify"
        assert component.name == "Notify"
        assert component.beta is True

    def test_inputs_configuration(self, component):
        """Test that inputs are properly configured."""
        expected_input_names = {"context_key", "input_value", "append"}
        input_names = {inp.name for inp in component.inputs}

        assert expected_input_names.issubset(input_names)
        assert len(component.inputs) >= 3

    def test_context_key_input_configuration(self, component):
        """Test context_key input configuration."""
        context_key_input = next((inp for inp in component.inputs if inp.name == "context_key"), None)

        assert context_key_input is not None
        assert context_key_input.display_name == "Context Key"
        assert context_key_input.required is True

    def test_input_value_input_configuration(self, component):
        """Test input_value input configuration."""
        input_value_input = next((inp for inp in component.inputs if inp.name == "input_value"), None)

        assert input_value_input is not None
        assert input_value_input.display_name == "Input Data"
        assert input_value_input.required is False
        assert input_value_input.input_types == ["Data", "Message", "DataFrame"]

    def test_append_input_configuration(self, component):
        """Test append input configuration."""
        append_input = next((inp for inp in component.inputs if inp.name == "append"), None)
        assert append_input is not None

    def test_outputs_configuration(self, component):
        """Test that outputs are properly configured."""
        assert len(component.outputs) >= 1

        result_output = next(out for out in component.outputs if out.name == "result")
        assert result_output.method == "notify_components"
        assert result_output.cache is False

    def test_component_beta_status(self, component):
        """Test that component is marked as beta."""
        assert hasattr(component, "beta")
        assert component.beta is True

    def test_component_inheritance(self, component):
        """Test that component properly inherits from Component base class."""
        from langflow.custom import Component

        assert isinstance(component, Component)

    @pytest.mark.asyncio
    async def test_notify_components_method_exists(self, component):
        """Test that notify_components method exists and is callable."""
        assert hasattr(component, "notify_components")
        assert callable(component.notify_components)

    @pytest.mark.asyncio
    async def test_notify_components_no_vertex_raises_error(self, component):
        """Test notify_components raises ValueError when component not in graph."""
        component.context_key = "test_key"
        component.input_value = Data(text="test")
        component.append = False
        component._vertex = None

        with pytest.raises(ValueError, match="Notify component must be used in a graph"):
            await component.notify_components()

    def test_notify_components_is_async(self, component):
        """Test that notify_components is properly defined as async."""
        import inspect

        assert inspect.iscoroutinefunction(component.notify_components)

    def test_output_method_mapping(self, component):
        """Test that output is correctly mapped to notify_components method."""
        result_output = next(out for out in component.outputs if out.name == "result")
        assert result_output.method == "notify_components"
        assert result_output.cache is False

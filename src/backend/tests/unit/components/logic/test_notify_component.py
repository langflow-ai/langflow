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
        assert hasattr(component, "inputs")
        assert len(component.inputs) >= 3  # context_key, input_value, append

        # Check input names
        input_names = [input_field.name for input_field in component.inputs]
        assert "context_key" in input_names
        assert "input_value" in input_names
        assert "append" in input_names

    def test_context_key_input(self, component):
        """Test context_key input configuration."""
        context_key_input = next((inp for inp in component.inputs if inp.name == "context_key"), None)

        assert context_key_input is not None
        assert context_key_input.display_name == "Context Key"
        assert context_key_input.required is True

    def test_input_value_input(self, component):
        """Test input_value input configuration."""
        input_value_input = next((inp for inp in component.inputs if inp.name == "input_value"), None)

        assert input_value_input is not None
        assert input_value_input.display_name == "Input Data"
        assert input_value_input.required is False
        assert input_value_input.input_types == ["Data", "Message", "DataFrame"]

    def test_append_input(self, component):
        """Test append input configuration."""
        append_input = next((inp for inp in component.inputs if inp.name == "append"), None)
        assert append_input is not None

    def test_outputs_configuration(self, component):
        """Test that outputs are properly configured."""
        assert hasattr(component, "outputs")
        assert len(component.outputs) >= 1

    @pytest.mark.asyncio
    async def test_notify_components_method_exists(self, component):
        """Test that notify_components method exists."""
        # Set up component inputs
        component.context_key = "test_key"
        component.input_value = Data(data={"message": "test notification"})
        component.append = False

        # The method should exist and be callable
        assert hasattr(component, "notify_components")
        assert callable(component.notify_components)

        # We won't test the full execution due to complex context setup requirements

    def test_component_beta_status(self, component):
        """Test that component is marked as beta."""
        assert hasattr(component, "beta")
        assert component.beta is True

    def test_component_inheritance(self, component):
        """Test that component properly inherits from Component base class."""
        from langflow.custom import Component

        assert isinstance(component, Component)

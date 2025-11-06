import pytest
from langflow.components.logic.notify import NotifyComponent
from langflow.schema.data import Data

from tests.base import ComponentTestBaseWithoutClient


class TestNotifyComponent(ComponentTestBaseWithoutClient):
    """Test cases for NotifyComponent."""

    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return NotifyComponent

    @pytest.fixture
    def default_kwargs(self):
        """Return the default kwargs for the component."""
        return {
            "context_key": "test_key",
            "input_value": None,
            "append": False,
        }

    @pytest.fixture
    def file_names_mapping(self):
        """Return an empty list since this component doesn't have version-specific files."""
        return []

    async def test_component_initialization(self, component_class, default_kwargs):
        """Test proper initialization of NotifyComponent."""
        component = await self.component_setup(component_class, default_kwargs)
        assert component.display_name == "Notify"
        assert component.description == "A component to generate a notification to Get Notified component."
        assert component.icon == "Notify"
        assert component.name == "Notify"
        assert component.beta is True

    async def test_inputs_configuration(self, component_class, default_kwargs):
        """Test that inputs are properly configured."""
        component = await self.component_setup(component_class, default_kwargs)
        expected_input_names = {"context_key", "input_value", "append"}
        input_names = {inp.name for inp in component.inputs}

        assert expected_input_names.issubset(input_names)
        assert len(component.inputs) >= 3

    async def test_context_key_input_configuration(self, component_class, default_kwargs):
        """Test context_key input configuration."""
        component = await self.component_setup(component_class, default_kwargs)
        context_key_input = next((inp for inp in component.inputs if inp.name == "context_key"), None)

        assert context_key_input is not None
        assert context_key_input.display_name == "Context Key"
        assert context_key_input.required is True

    async def test_input_value_input_configuration(self, component_class, default_kwargs):
        """Test input_value input configuration."""
        component = await self.component_setup(component_class, default_kwargs)
        input_value_input = next((inp for inp in component.inputs if inp.name == "input_value"), None)

        assert input_value_input is not None
        assert input_value_input.display_name == "Input Data"
        assert input_value_input.required is False
        assert input_value_input.input_types == ["Data", "Message", "DataFrame"]

    async def test_append_input_configuration(self, component_class, default_kwargs):
        """Test append input configuration."""
        component = await self.component_setup(component_class, default_kwargs)
        append_input = next((inp for inp in component.inputs if inp.name == "append"), None)
        assert append_input is not None

    async def test_outputs_configuration(self, component_class, default_kwargs):
        """Test that outputs are properly configured."""
        component = await self.component_setup(component_class, default_kwargs)
        assert len(component.outputs) >= 1

        result_output = next(out for out in component.outputs if out.name == "result")
        assert result_output.method == "notify_components"
        assert result_output.cache is False

    async def test_component_beta_status(self, component_class, default_kwargs):
        """Test that component is marked as beta."""
        component = await self.component_setup(component_class, default_kwargs)
        assert hasattr(component, "beta")
        assert component.beta is True

    async def test_component_inheritance(self, component_class, default_kwargs):
        """Test that component properly inherits from Component base class."""
        component = await self.component_setup(component_class, default_kwargs)
        from langflow.custom import Component

        assert isinstance(component, Component)

    @pytest.mark.asyncio
    async def test_notify_components_method_exists(self, component_class, default_kwargs):
        """Test that notify_components method exists and is callable."""
        component = await self.component_setup(component_class, default_kwargs)
        assert hasattr(component, "notify_components")
        assert callable(component.notify_components)

    @pytest.mark.asyncio
    async def test_notify_components_no_vertex_raises_error(self, component_class, default_kwargs):
        """Test notify_components raises ValueError when component not in graph."""
        component = await self.component_setup(component_class, default_kwargs)
        component.context_key = "test_key"
        component.input_value = Data(text="test")
        component.append = False
        component._vertex = None

        with pytest.raises(ValueError, match="Notify component must be used in a graph"):
            await component.notify_components()

    async def test_notify_components_is_async(self, component_class, default_kwargs):
        """Test that notify_components is properly defined as async."""
        component = await self.component_setup(component_class, default_kwargs)
        import inspect

        assert inspect.iscoroutinefunction(component.notify_components)

    async def test_output_method_mapping(self, component_class, default_kwargs):
        """Test that output is correctly mapped to notify_components method."""
        component = await self.component_setup(component_class, default_kwargs)
        result_output = next(out for out in component.outputs if out.name == "result")
        assert result_output.method == "notify_components"
        assert result_output.cache is False

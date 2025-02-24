import pytest
from langflow.components.inputs import TextInputComponent

from tests.base import ComponentTestBaseWithoutClient


class TestTextInputComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return TextInputComponent

    @pytest.fixture
    def default_kwargs(self):
        return {"input_value": "Sample text input"}

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.19", "module": "inputs", "file_name": "TextInput"},
            {"version": "1.1.0", "module": "inputs", "file_name": "text"},
            {"version": "1.1.1", "module": "inputs", "file_name": "text"},
        ]

    def test_text_response(self, component_class, default_kwargs):
        # Arrange
        component = component_class(**default_kwargs)

        # Act
        result = component.text_response()

        # Assert
        assert result is not None
        assert result.text == "Sample text input"

    async def test_latest_version(self, component_class, default_kwargs):
        """Test that the component works with the latest version."""
        component_instance = await self.component_setup(component_class, default_kwargs)

        result = await component_instance.run()

        assert result is not None, "Component returned None for the latest version."

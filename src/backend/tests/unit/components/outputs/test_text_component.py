import pytest

from langflow.components.outputs import TextOutputComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestTextOutputComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return TextOutputComponent

    @pytest.fixture
    def default_kwargs(self):
        return {"input_value": "Hello, World!"}

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "text_output", "file_name": "TextOutput"},
        ]

    def test_text_response(self, component_class, default_kwargs):
        # Arrange
        component = component_class(**default_kwargs)

        # Act
        result = component.text_response()

        # Assert
        assert result is not None
        assert result.text == "Hello, World!"
        assert component.status == "Hello, World!"

    async def test_latest_version(self, component_class, default_kwargs):
        """Test that the component works with the latest version."""
        component_instance = await self.component_setup(component_class, default_kwargs)
        result = await component_instance.run()
        assert result is not None, "Component returned None for the latest version."

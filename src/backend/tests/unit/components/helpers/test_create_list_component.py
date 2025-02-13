import pytest

from langflow.components.helpers import CreateListComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestCreateListComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return CreateListComponent

    @pytest.fixture
    def default_kwargs(self):
        return {"texts": ["Hello", "World"], "_session_id": "123"}

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_create_list(self, component_class, default_kwargs):
        # Arrange
        component = component_class(**default_kwargs)

        # Act
        result = component.create_list()

        # Assert
        assert result is not None
        assert len(result) == 2
        assert result[0].text == "Hello"
        assert result[1].text == "World"

    async def test_latest_version(self, component_class, default_kwargs):
        # Arrange
        component_instance = await self.component_setup(component_class, default_kwargs)

        # Act
        result = await component_instance.run()

        # Assert
        assert result is not None, "Component returned None for the latest version."

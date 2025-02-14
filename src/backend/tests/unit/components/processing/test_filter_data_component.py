import pytest

from langflow.components.processing.filter_data import FilterDataComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestFilterDataComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return FilterDataComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "data": {"key1": "value1", "key2": "value2", "key3": "value3"},
            "filter_criteria": ["key1", "key3"],
        }

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_filter_data(self, component_class, default_kwargs):
        # Arrange
        component = component_class(**default_kwargs)

        # Act
        result = component.filter_data()

        # Assert
        assert result is not None
        assert isinstance(result, Data)
        assert result.data == {"key1": "value1", "key3": "value3"}
        assert "key2" not in result.data

    async def test_latest_version(self, component_class, default_kwargs):
        component_instance = await self.component_setup(component_class, default_kwargs)
        result = await component_instance.run()
        assert result is not None, "Component returned None for the latest version."

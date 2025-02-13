import pytest

from langflow.components.deactivated import ExtractKeyFromDataComponent
from langflow.schema import Data
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestExtractKeyFromDataComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return ExtractKeyFromDataComponent

    @pytest.fixture
    def default_kwargs(self):
        return {}

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_build_with_valid_keys(self, component_class):
        # Arrange
        data = Data(data={"key1": "value1", "key2": "value2"})
        keys = ["key1", "key2"]
        component = component_class()

        # Act
        result = component.build(data, keys)

        # Assert
        assert result.data == {"key1": "value1", "key2": "value2"}
        assert component.status.data == {"key1": "value1", "key2": "value2"}

    def test_build_with_invalid_key_and_silent_error(self, component_class):
        # Arrange
        data = Data(data={"key1": "value1"})
        keys = ["key1", "key2"]  # key2 does not exist
        component = component_class()

        # Act
        result = component.build(data, keys, silent_error=True)

        # Assert
        assert result.data == {"key1": "value1"}
        assert component.status.data == {"key1": "value1"}

    def test_build_with_invalid_key_and_raise_error(self, component_class):
        # Arrange
        data = Data(data={"key1": "value1"})
        keys = ["key1", "key2"]  # key2 does not exist
        component = component_class()

        # Act & Assert
        with pytest.raises(KeyError, match="The key 'key2' does not exist in the data."):
            component.build(data, keys, silent_error=False)

    def test_build_with_empty_keys(self, component_class):
        # Arrange
        data = Data(data={"key1": "value1"})
        keys = []
        component = component_class()

        # Act
        result = component.build(data, keys)

        # Assert
        assert result.data == {}
        assert component.status.data == {}

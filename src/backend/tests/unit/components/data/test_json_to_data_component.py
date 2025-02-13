from pathlib import Path

import pytest
from langflow.components.data import JSONToDataComponent
from langflow.schema import Data

from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestJSONToDataComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return JSONToDataComponent

    @pytest.fixture
    def default_kwargs(self):
        return {}

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_convert_json_from_file(self, component_class):
        # Arrange
        json_content = '{"key": "value"}'
        with Path.open("test.json", "w") as f:
            f.write(json_content)

        component = component_class(json_file="test.json")

        # Act
        result = component.convert_json_to_data()

        # Assert
        assert result is not None
        assert isinstance(result, Data)
        assert result.data == {"key": "value"}

    def test_convert_json_from_path(self, component_class):
        # Arrange
        json_content = '{"key": "value"}'
        with Path.open("test_path.json", "w") as f:
            f.write(json_content)

        component = component_class(json_path="test_path.json")

        # Act
        result = component.convert_json_to_data()

        # Assert
        assert result is not None
        assert isinstance(result, Data)
        assert result.data == {"key": "value"}

    def test_convert_json_string(self, component_class):
        # Arrange
        json_string = '{"key": "value"}'
        component = component_class(json_string=json_string)

        # Act
        result = component.convert_json_to_data()

        # Assert
        assert result is not None
        assert isinstance(result, Data)
        assert result.data == {"key": "value"}

    def test_multiple_inputs(self, component_class):
        # Arrange
        component = component_class(json_file="test.json", json_string='{"key": "value"}')

        # Act & Assert
        with pytest.raises(ValueError, match="Please provide exactly one of: JSON file, file path, or JSON string."):
            component.convert_json_to_data()

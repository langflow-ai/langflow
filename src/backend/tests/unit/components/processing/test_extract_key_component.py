import pytest

from langflow.components.processing import ExtractDataKeyComponent
from langflow.schema import Data
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestExtractDataKeyComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return ExtractDataKeyComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "data_input": Data(data={"name": "John", "age": 30}),
            "key": "name",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "extract_data_key", "file_name": "ExtractDataKey"},
        ]

    def test_extract_key_single_data(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = component.extract_key()
        assert isinstance(result, Data)
        assert result.data["name"] == "John"

    def test_extract_key_list_data(self, component_class):
        data_input = [Data(data={"name": "John"}), Data(data={"name": "Jane"})]
        component = component_class(data_input=data_input, key="name")
        result = component.extract_key()
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0].data["name"] == "John"
        assert result[1].data["name"] == "Jane"

    def test_extract_key_not_found(self, component_class):
        component = component_class(data_input=Data(data={"name": "John"}), key="nonexistent_key")
        result = component.extract_key()
        assert isinstance(result, Data)
        assert "error" in result.data
        assert result.data["error"] == "Key 'nonexistent_key' not found in Data object."

    def test_invalid_input(self, component_class):
        component = component_class(data_input="invalid_input", key="name")
        result = component.extract_key()
        assert isinstance(result, Data)
        assert "error" in result.data
        assert result.data["error"] == "Invalid input. Expected Data object or list of Data objects."

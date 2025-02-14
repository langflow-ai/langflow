import pytest

from langflow.components.processing import ParseJSONDataComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestParseJSONDataComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return ParseJSONDataComponent

    @pytest.fixture
    def default_kwargs(self):
        return {"input_value": '{"name": "John", "age": 30}', "query": ".name"}

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "parsers", "file_name": "ParseJSONData"},
        ]

    def test_filter_data_valid_json(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = component.filter_data()
        assert len(result) == 1
        assert result[0].data == "John"

    def test_filter_data_invalid_json(self, component_class):
        component = component_class(input_value="invalid json", query=".name")
        with pytest.raises(ValueError, match="Invalid JSON:"):
            component.filter_data()

    def test_filter_data_empty_input(self, component_class):
        component = component_class(input_value=None, query=".name")
        result = component.filter_data()
        assert result == []

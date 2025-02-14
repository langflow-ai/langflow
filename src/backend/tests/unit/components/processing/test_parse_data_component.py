import pytest

from langflow.components.processing import ParseDataComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestParseDataComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return ParseDataComponent

    @pytest.fixture
    def default_kwargs(self):
        return {"data": [{"text": "Hello"}, {"text": "World"}], "template": "{text}", "sep": ", "}

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "data", "file_name": "ParseData"},
        ]

    def test_parse_data(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = component.parse_data()
        assert result is not None
        assert result.text == "Hello, World"

    def test_parse_data_as_list(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = component.parse_data_as_list()
        assert result is not None
        assert len(result) == 2
        assert result[0].text == "Hello"
        assert result[1].text == "World"

    def test_component_latest_version(self, component_class, default_kwargs):
        result = component_class(**default_kwargs)()
        assert result is not None

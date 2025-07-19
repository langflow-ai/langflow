import pytest
from langflow.components.processing.jq import JQComponent
from langflow.schema import Data, DataFrame

from tests.base import ComponentTestBaseWithoutClient


class TestJQComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return JQComponent

    @pytest.fixture
    def default_kwargs(self):
        return {"jq": ".test", "input_json": Data(data={"test": "it works"})}

    @pytest.fixture
    def file_names_mapping(self):
        return []

    async def test_extracts_string(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.jq = ".test"
        component.input_json = Data(data={"test": "it works"})

        result = component.build_output_string()
        assert result == "it works"

    async def test_extracts_object(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.jq = '{"result":.test, "value": .number}'
        component.input_json = Data(data={"test": "it works", "number": 32})

        result = component.build_output_object()
        assert result == Data(data={"result": "it works", "value": 32})

    async def test_extracts_array(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.jq = ".array"
        component.input_json = Data(data={"array": [{"val": 1}, {"val": 2}, {"val": 3}], "number": 32})

        result = component.build_output_array()
        assert result == DataFrame(data=[{"val": 1}, {"val": 2}, {"val": 3}])

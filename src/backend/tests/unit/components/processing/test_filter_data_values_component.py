import pytest
from langflow.components.processing.filter_data_values import DataFilterComponent

from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestDataFilterComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return DataFilterComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "input_data": [{"route": "CMIP"}, {"route": "GFS"}, {"route": "CMIP"}],
            "filter_key": "route",
            "filter_value": "CMIP",
            "operator": "equals",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_filter_data_equals(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = component.filter_data()
        assert len(result) == 2
        assert all(item.data["route"] == "CMIP" for item in result)

    def test_filter_data_not_equals(self, component_class):
        kwargs = {
            "input_data": [{"route": "CMIP"}, {"route": "GFS"}, {"route": "CMIP"}],
            "filter_key": "route",
            "filter_value": "GFS",
            "operator": "not equals",
        }
        component = component_class(**kwargs)
        result = component.filter_data()
        assert len(result) == 2
        assert all(item.data["route"] != "GFS" for item in result)

    def test_filter_data_contains(self, component_class):
        kwargs = {
            "input_data": [{"route": "CMIP"}, {"route": "GFS"}, {"route": "CMIP"}],
            "filter_key": "route",
            "filter_value": "MI",
            "operator": "contains",
        }
        component = component_class(**kwargs)
        result = component.filter_data()
        assert len(result) == 2
        assert all("MI" in item.data["route"] for item in result)

    def test_filter_data_empty_input(self, component_class):
        kwargs = {
            "input_data": [],
            "filter_key": "route",
            "filter_value": "CMIP",
            "operator": "equals",
        }
        component = component_class(**kwargs)
        result = component.filter_data()
        assert result == []
        assert component.status == "Input data is empty."

    def test_filter_data_missing_key(self, component_class):
        kwargs = {
            "input_data": [{"route": "CMIP"}, {"other_key": "GFS"}],
            "filter_key": "route",
            "filter_value": "CMIP",
            "operator": "equals",
        }
        component = component_class(**kwargs)
        result = component.filter_data()
        assert len(result) == 1
        assert result[0].data["route"] == "CMIP"
        assert component.status == "Warning: Some items don't have the key 'route' or are not dictionaries."

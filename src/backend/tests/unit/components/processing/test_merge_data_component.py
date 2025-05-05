import pytest
from langflow.components.processing.merge_data import MergeDataComponent

from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestMergeDataComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return MergeDataComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "data_inputs": [
                {"data": {"column1": "value1", "column2": "value2"}},
                {"data": {"column1": "value3", "column2": "value4"}},
            ],
            "operation": "Concatenate",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "data_combiner", "file_name": "MergeDataComponent"},
        ]

    def test_combine_data_concatenate(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = component.combine_data()
        assert result is not None
        assert len(result.data) == 1
        assert result.data[0]["column1"] == "value1\nvalue3"
        assert result.data[0]["column2"] == "value2\nvalue4"

    def test_combine_data_append(self, component_class):
        default_kwargs = {
            "data_inputs": [
                {"data": {"column1": "value1"}},
                {"data": {"column1": "value2"}},
            ],
            "operation": "Append",
        }
        component = component_class(**default_kwargs)
        result = component.combine_data()
        assert result is not None
        assert len(result.data) == 2
        assert result.data[0]["column1"] == "value1"
        assert result.data[1]["column1"] == "value2"

    def test_combine_data_merge(self, component_class):
        default_kwargs = {
            "data_inputs": [
                {"data": {"column1": "value1", "column2": "value2"}},
                {"data": {"column1": "value3", "column2": "value2"}},
            ],
            "operation": "Merge",
        }
        component = component_class(**default_kwargs)
        result = component.combine_data()
        assert result is not None
        assert len(result.data) == 1
        assert result.data[0]["column1"] == "value3"
        assert result.data[0]["column2"] == "value2"

    def test_combine_data_join(self, component_class):
        default_kwargs = {
            "data_inputs": [
                {"data": {"column1": "value1"}},
                {"data": {"column2": "value2"}},
            ],
            "operation": "Join",
        }
        component = component_class(**default_kwargs)
        result = component.combine_data()
        assert result is not None
        assert len(result.data) == 1
        assert result.data[0]["column1"] == "value1"
        assert result.data[0]["column2_doc2"] == "value2"

    def test_combine_data_insufficient_inputs(self, component_class):
        default_kwargs = {
            "data_inputs": [
                {"data": {"column1": "value1"}},
            ],
            "operation": "Concatenate",
        }
        component = component_class(**default_kwargs)
        result = component.combine_data()
        assert result is not None
        assert len(result.data) == 0

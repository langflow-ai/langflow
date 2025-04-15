import pytest
from langflow.components.deactivated import MergeDataComponent
from langflow.schema import Data
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
                Data(text_key="input1", data={"key1": "value1", "key2": "value2"}),
                Data(text_key="input2", data={"key2": "value2", "key3": "value3"}),
            ],
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "merge_data", "file_name": "MergeData"},
        ]

    def test_merge_data_success(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = component.merge_data()

        assert len(result) == 2
        assert result[0].data == {"key1": "value1", "key2": "value2", "key3": ""}
        assert result[1].data == {"key1": "", "key2": "value2", "key3": "value3"}

    def test_merge_data_empty_input(self, component_class):
        component = component_class(data_inputs=[])
        result = component.merge_data()

        assert result == []

    def test_merge_data_type_error(self, component_class):
        component = component_class(data_inputs=["not_a_data_object"])

        with pytest.raises(TypeError, match="All items in data_inputs must be of type Data"):
            component.merge_data()

import pytest
from langflow.components.processing import SelectDataComponent

from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestSelectDataComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return SelectDataComponent

    @pytest.fixture
    def default_kwargs(self):
        return {"data_list": ["data1", "data2", "data3"], "data_index": 1, "_session_id": "123"}

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "select_data", "file_name": "SelectData"},
        ]

    async def test_select_data_within_bounds(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = await component.select_data()
        assert result == "data2"
        assert component.status == "data2"

    async def test_select_data_out_of_bounds(self, component_class):
        component = component_class(data_list=["data1", "data2"], data_index=5)
        with pytest.raises(ValueError, match="Selected index 5 is out of range."):
            await component.select_data()

    async def test_select_data_negative_index(self, component_class):
        component = component_class(data_list=["data1", "data2"], data_index=-1)
        with pytest.raises(ValueError, match="Selected index -1 is out of range."):
            await component.select_data()

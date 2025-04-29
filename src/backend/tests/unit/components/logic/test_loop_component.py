import pytest
from langflow.components.logic import LoopComponent
from langflow.schema import Data

from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestLoopComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return LoopComponent

    @pytest.fixture
    def default_kwargs(self):
        return {"data": [Data(text="Item 1"), Data(text="Item 2"), Data(text="Item 3")], "_session_id": "123"}

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "loops", "file_name": "Loop"},
        ]

    def test_initialize_data(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.initialize_data()
        assert component.ctx[f"{component._id}_initialized"] is True
        assert len(component.ctx[f"{component._id}_data"]) == 3

    def test_item_output(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.initialize_data()

        item1 = component.item_output()
        assert item1.text == "Item 1"

        item2 = component.item_output()
        assert item2.text == "Item 2"

        item3 = component.item_output()
        assert item3.text == "Item 3"

        done_item = component.item_output()
        assert done_item.text == ""

    def test_done_output(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.initialize_data()

        component.item_output()  # Process first item
        component.item_output()  # Process second item
        component.item_output()  # Process third item

        done_output = component.done_output()
        assert isinstance(done_output, list)
        assert len(done_output) == 3
        assert done_output == [Data(text="Item 1"), Data(text="Item 2"), Data(text="Item 3")]

    def test_aggregated_output(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.initialize_data()

        component.item_output()  # Process first item
        component.aggregated_output()  # Aggregate first item

        component.item_output()  # Process second item
        component.aggregated_output()  # Aggregate second item

        aggregated = component.ctx[f"{component._id}_aggregated"]
        assert len(aggregated) == 2
        assert aggregated == [Data(text="Item 1"), Data(text="Item 2")]

import pytest
from lfx.components.processing.filter_data_values import DataFilterComponent
from lfx.schema.data import Data
from lfx.schema.message import Message

from tests.base import ComponentTestBaseWithoutClient


class TestFilterDataValuesComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return DataFilterComponent

    @pytest.fixture
    def default_kwargs(self):
        """Return the default kwargs for the component."""
        return {
            "input_data": [Data(data={"route": "CMIP"}), Data(data={"route": "OTHER"})],
            "filter_key": "route",
            "filter_value": "CMIP",
            "operator": "equals",
        }

    @pytest.fixture
    def file_names_mapping(self):
        """Return an empty list because this legacy component has no versioned files."""
        return []

    @pytest.mark.parametrize(
        ("filter_key", "filter_value"),
        [
            ("route", "CMIP"),
            (Data(data={"text": "route"}), Message(text="CMIP")),
            (Message(text="route"), Data(data={"text": "CMIP"})),
        ],
    )
    def test_filter_data_accepts_string_and_data_text_inputs(self, filter_key, filter_value):
        """Test filtering with plain strings and connected Data or Message text values."""
        component = DataFilterComponent()
        component.input_data = [Data(data={"route": "CMIP"}), Data(data={"route": "OTHER"})]
        component.filter_key = filter_key
        component.filter_value = filter_value
        component.operator = "equals"

        assert component.filter_data() == [component.input_data[0]]

    @pytest.mark.parametrize("value", [None, Data(data={"text": None}), Message(text="")])
    def test_filter_data_treats_empty_text_input_as_missing(self, value):
        """Test that empty or missing filter text leaves input data unchanged."""
        component = DataFilterComponent()
        original_data = [Data(data={"route": "CMIP"})]
        component.input_data = original_data
        component.filter_key = "route"
        component.filter_value = value
        component.operator = "equals"

        assert component.filter_data() == original_data
        assert component.status == "Filter key or value is missing."

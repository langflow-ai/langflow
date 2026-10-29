import pytest
from lfx.components.processing.filter_data_values import DataFilterComponent
from lfx.schema.data import Data
from lfx.schema.message import Message


@pytest.mark.parametrize(
    ("filter_key", "filter_value"),
    [
        ("route", "CMIP"),
        (Data(data={"text": "route"}), Message(text="CMIP")),
        (Message(text="route"), Data(data={"text": "CMIP"})),
    ],
)
def test_filter_data_accepts_string_and_data_text_inputs(filter_key, filter_value):
    component = DataFilterComponent()
    component.input_data = [Data(data={"route": "CMIP"}), Data(data={"route": "OTHER"})]
    component.filter_key = filter_key
    component.filter_value = filter_value
    component.operator = "equals"

    assert component.filter_data() == [component.input_data[0]]


@pytest.mark.parametrize("value", [None, Data(data={"text": None}), Message(text="")])
def test_filter_data_treats_empty_text_input_as_missing(value):
    component = DataFilterComponent()
    original_data = [Data(data={"route": "CMIP"})]
    component.input_data = original_data
    component.filter_key = "route"
    component.filter_value = value
    component.operator = "equals"

    assert component.filter_data() == original_data
    assert component.status == "Filter key or value is missing."

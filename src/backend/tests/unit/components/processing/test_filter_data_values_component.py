import pytest
from lfx.components.processing.filter_data_values import DataFilterComponent
from lfx.schema import Data, Message

from tests.base import ComponentTestBaseWithoutClient


class TestDataFilterComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        """Return the legacy Filter Values component."""
        return DataFilterComponent

    @pytest.fixture
    def default_kwargs(self):
        """Provide valid ordinary text inputs for the component lifecycle."""
        return {"input_data": [Data(data={"route": "CMIP"})], "filter_key": "route", "filter_value": "CMIP"}

    @pytest.fixture
    def file_names_mapping(self):
        """Historical component fixtures are not available for this test class."""
        return []

    @pytest.mark.parametrize(
        ("operator", "value", "expected"),
        [
            ("equals", "CMIP", ["CMIP"]),
            ("not equals", "CMIP", ["OTHER"]),
            ("contains", "MI", ["CMIP"]),
            ("starts with", "CM", ["CMIP"]),
            ("ends with", "IP", ["CMIP"]),
        ],
    )
    def test_filter_text_inputs(self, operator, value, expected):
        """All five comparisons must accept literal text and skip absent keys."""
        component = DataFilterComponent().set(
            input_data=[Data(data={"route": "CMIP"}), Data(data={"route": "OTHER"}), Data(data={"missing": "key"})],
            filter_key="route",
            filter_value=value,
            operator=operator,
        )
        assert [item.data["route"] for item in component.filter_data()] == expected

    @pytest.mark.parametrize("input_type", [Data, Message, dict])
    def test_connected_text_inputs(self, input_type):
        """The validated component path accepts text-bearing connected inputs."""
        component = DataFilterComponent()
        component.set_attributes(
            {
                "input_data": [Data(data={"route": "CMIP"}), Data(data={"route": "OTHER"})],
                "filter_key": input_type(text="route"),
                "filter_value": input_type(text="CMIP"),
            }
        )
        assert [item.data["route"] for item in component.filter_data()] == ["CMIP"]

    @pytest.mark.parametrize(("key", "value"), [("", "CMIP"), ("route", "")])
    def test_missing_filter_returns_input(self, key, value):
        """Missing filter text retains the existing pass-through behavior."""
        items = [Data(data={"route": "CMIP"})]
        component = DataFilterComponent().set(input_data=items, filter_key=key, filter_value=value)
        assert component.filter_data() == items

    def test_empty_input(self):
        """An empty record list returns without reading a message attribute."""
        component = DataFilterComponent().set(input_data=[], filter_key="route", filter_value="CMIP")
        assert component.filter_data() == []

    @pytest.mark.parametrize("input_type", [Data, Message])
    def test_sdk_text_objects(self, input_type):
        """Direct SDK objects retain their text extraction compatibility."""
        component = DataFilterComponent().set(
            input_data=[Data(data={"route": "CMIP"}), Data(data={"route": "OTHER"})],
            filter_key=input_type(text="route"),
            filter_value=input_type(text="CMIP"),
        )
        assert isinstance(component.filter_key, input_type)
        assert isinstance(component.filter_value, input_type)
        assert [item.data["route"] for item in component.filter_data()] == ["CMIP"]

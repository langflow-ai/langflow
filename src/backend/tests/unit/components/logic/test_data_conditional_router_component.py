import pytest

from langflow.components.logic import DataConditionalRouterComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestDataConditionalRouterComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return DataConditionalRouterComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "data_input": [{"key_name": "value1"}, {"key_name": "value2"}],
            "key_name": "key_name",
            "operator": "equals",
            "compare_value": "value1",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "data_conditional_router", "file_name": "DataConditionalRouter"},
        ]

    def test_process_data_with_true_condition(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = component.process_data()
        assert len(result) == 1
        assert result[0].data["key_name"] == "value1"

    def test_process_data_with_false_condition(self, component_class, default_kwargs):
        default_kwargs["compare_value"] = "value3"
        component = component_class(**default_kwargs)
        result = component.process_data()
        assert len(result) == 1
        assert result[0].data["key_name"] == "value2"

    def test_validate_input_with_valid_data(self, component_class):
        component = component_class(data_input={"key_name": "value"}, key_name="key_name")
        assert component.validate_input(component.data_input) is True

    def test_validate_input_with_invalid_data(self, component_class):
        component = component_class(data_input={"invalid_key": "value"}, key_name="key_name")
        assert component.validate_input(component.data_input) is False
        assert component.status == "Key 'key_name' not found in Data"

    def test_compare_values_equals_operator(self, component_class):
        component = component_class()
        assert component.compare_values("value", "value", "equals") is True
        assert component.compare_values("value", "other", "equals") is False

    def test_compare_values_boolean_validator(self, component_class):
        component = component_class()
        assert component.compare_values("true", "", "boolean validator") is True
        assert component.compare_values("false", "", "boolean validator") is False

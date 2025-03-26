import pytest
from langflow.components.deactivated import SelectivePassThroughComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestSelectivePassThroughComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return SelectivePassThroughComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "input_value": "Hello World",
            "comparison_value": "Hello World",
            "operator": "equals",
            "value_to_pass": "Passed!",
            "case_sensitive": False,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "selective_pass_through", "file_name": "SelectivePassThrough"},
        ]

    def test_pass_through_when_condition_met(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = component.pass_through()
        assert result == "Passed!"
        assert component.status == "Passed!"

    def test_no_pass_through_when_condition_not_met(self, component_class, default_kwargs):
        default_kwargs["operator"] = "not equals"
        component = component_class(**default_kwargs)
        result = component.pass_through()
        assert result == ""
        assert component.status == ""

    def test_case_sensitive_condition(self, component_class, default_kwargs):
        default_kwargs["case_sensitive"] = True
        default_kwargs["comparison_value"] = "hello world"
        component = component_class(**default_kwargs)
        result = component.pass_through()
        assert result == ""
        assert component.status == ""

    def test_contains_operator(self, component_class, default_kwargs):
        default_kwargs["operator"] = "contains"
        default_kwargs["comparison_value"] = "World"
        component = component_class(**default_kwargs)
        result = component.pass_through()
        assert result == "Passed!"
        assert component.status == "Passed!"

    def test_starts_with_operator(self, component_class, default_kwargs):
        default_kwargs["operator"] = "starts with"
        default_kwargs["comparison_value"] = "Hello"
        component = component_class(**default_kwargs)
        result = component.pass_through()
        assert result == "Passed!"
        assert component.status == "Passed!"

    def test_ends_with_operator(self, component_class, default_kwargs):
        default_kwargs["operator"] = "ends with"
        default_kwargs["comparison_value"] = "World"
        component = component_class(**default_kwargs)
        result = component.pass_through()
        assert result == "Passed!"
        assert component.status == "Passed!"

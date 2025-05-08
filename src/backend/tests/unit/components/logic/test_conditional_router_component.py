import pytest
from langflow.components.logic import ConditionalRouterComponent

from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestConditionalRouterComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return ConditionalRouterComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "input_text": "Hello World",
            "match_text": "World",
            "operator": "contains",
            "case_sensitive": False,
            "message": "Matched!",
            "max_iterations": 10,
            "default_route": "false_result",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "conditional_router", "file_name": "ConditionalRouter"},
        ]

    def test_true_response(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = component.true_response()
        assert result.content == "Matched!"
        assert component.status == "Matched!"

    def test_false_response(self, component_class, default_kwargs):
        default_kwargs["input_text"] = "Goodbye World"
        component = component_class(**default_kwargs)
        result = component.false_response()
        assert result.content == "Matched!"
        assert component.status == "Matched!"

    def test_evaluate_condition_equals(self, component_class, default_kwargs):
        default_kwargs["operator"] = "equals"
        component = component_class(**default_kwargs)
        result = component.evaluate_condition("Hello World", "Hello World", "equals", case_sensitive=False)
        assert result is True

    def test_evaluate_condition_not_equals(self, component_class, default_kwargs):
        default_kwargs["operator"] = "not equals"
        component = component_class(**default_kwargs)
        result = component.evaluate_condition("Hello World", "Goodbye World", "not equals", case_sensitive=False)
        assert result is True

    def test_evaluate_condition_contains(self, component_class, default_kwargs):
        default_kwargs["operator"] = "contains"
        component = component_class(**default_kwargs)
        result = component.evaluate_condition("Hello World", "World", "contains", case_sensitive=False)
        assert result is True

    def test_evaluate_condition_starts_with(self, component_class, default_kwargs):
        default_kwargs["operator"] = "starts with"
        component = component_class(**default_kwargs)
        result = component.evaluate_condition("Hello World", "Hello", "starts with", case_sensitive=False)
        assert result is True

    def test_evaluate_condition_ends_with(self, component_class, default_kwargs):
        default_kwargs["operator"] = "ends with"
        component = component_class(**default_kwargs)
        result = component.evaluate_condition("Hello World", "World", "ends with", case_sensitive=False)
        assert result is True

    def test_evaluate_condition_regex(self, component_class, default_kwargs):
        default_kwargs["operator"] = "regex"
        component = component_class(**default_kwargs)
        result = component.evaluate_condition("Hello World", r"^Hello", "regex", case_sensitive=False)
        assert result is True

    def test_iterate_and_stop_once(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.iterate_and_stop_once("false_result")
        assert component.ctx.get(f"{component._id}_iteration") == 1

    def test_update_build_config(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        build_config = {}
        updated_config = component.update_build_config(build_config, "regex", "operator")
        assert "case_sensitive" not in updated_config

        updated_config = component.update_build_config(build_config, "contains", "operator")
        assert "case_sensitive" in updated_config

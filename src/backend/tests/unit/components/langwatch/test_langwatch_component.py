import pytest
from langflow.components.langwatch import LangWatchComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestLangWatchComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return LangWatchComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "api_key": "test_api_key",
            "evaluator_name": "test_evaluator",
            "input": "Sample input",
            "output": "Sample output",
            "expected_output": "Expected output",
            "contexts": "context1,context2",
            "timeout": 30,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "langwatch", "file_name": "LangWatch"},
            {"version": "1.1.0", "module": "langwatch", "file_name": "langwatch"},
        ]

    def test_get_evaluators(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        evaluators = component.get_evaluators()
        assert isinstance(evaluators, dict)
        assert "test_evaluator" in evaluators

    async def test_evaluate_component(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = await component.evaluate()
        assert result is not None
        assert isinstance(result.data, dict)

    def test_update_build_config(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        build_config = {}
        updated_config = component.update_build_config(build_config, "test_evaluator")
        assert "evaluator_name" in updated_config
        assert updated_config["evaluator_name"]["value"] == "test_evaluator"

    async def test_dynamic_inputs_creation(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        evaluator = {
            "requiredFields": ["input", "output"],
            "optionalFields": ["contexts"],
            "settings": {},
        }
        dynamic_inputs = component.get_dynamic_inputs(evaluator)
        assert "input" in dynamic_inputs
        assert "output" in dynamic_inputs
        assert "contexts" in dynamic_inputs
        assert isinstance(dynamic_inputs["contexts"], MultilineInput)

    async def test_evaluate_missing_api_key(self, component_class):
        component = component_class(api_key="", evaluator_name="test_evaluator")
        result = await component.evaluate()
        assert result.data["error"] == "API key is required"

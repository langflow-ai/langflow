import pytest
from langflow.components.processing import LLMRouterComponent

from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestLLMRouterComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return LLMRouterComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "models": ["model_a", "model_b"],
            "input_value": {"text": "What is the weather today?"},
            "judge_llm": "judge_model",
            "optimization": "balanced",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "llm_router", "file_name": "LLMRouter"},
            {"version": "1.1.0", "module": "llm_router", "file_name": "llm_router"},
        ]

    async def test_route_to_model_success(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = await component.route_to_model()
        assert result is not None
        assert isinstance(result, Message)

    async def test_route_to_model_missing_inputs(self, component_class):
        component = component_class(models=[], input_value=None, judge_llm=None)
        with pytest.raises(ValueError, match=component.MISSING_INPUTS_MSG):
            await component.route_to_model()

    async def test_get_selected_model(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        await component.route_to_model()
        selected_model = component.get_selected_model()
        assert selected_model is not None
        assert selected_model in default_kwargs["models"]

    async def test_model_specs_fetching(self, component_class):
        component = component_class()
        model_specs = component._get_model_specs("model_a")
        assert "Model: model_a" in model_specs
        assert "Description:" in model_specs

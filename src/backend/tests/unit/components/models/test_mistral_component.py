import pytest

from langflow.components.models import MistralAIModelComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestMistralAIModelComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return MistralAIModelComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "max_tokens": 100,
            "model_name": "codestral-latest",
            "mistral_api_base": "https://api.mistral.ai/v1",
            "api_key": "test_api_key",
            "temperature": 0.5,
            "max_retries": 5,
            "timeout": 60,
            "max_concurrent_requests": 3,
            "top_p": 1,
            "random_seed": 1,
            "safe_mode": True,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "mistral", "file_name": "MistralAIModelComponent"},
        ]

    async def test_build_model(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        model = component.build_model()
        assert model is not None
        assert model.model_name == default_kwargs["model_name"]
        assert model.max_tokens == default_kwargs["max_tokens"]
        assert model.temperature == default_kwargs["temperature"]

    def test_component_latest_version(self, component_class, default_kwargs):
        result = component_class(**default_kwargs)()
        assert result is not None

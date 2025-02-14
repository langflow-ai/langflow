import pytest

from langflow.components.models import PerplexityComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestPerplexityComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return PerplexityComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "model_name": "llama-3.1-sonar-small-128k-online",
            "max_output_tokens": 100,
            "api_key": "test_api_key",
            "temperature": 0.75,
            "top_p": 0.9,
            "n": 1,
            "top_k": 50,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "perplexity", "file_name": "Perplexity"},
            {"version": "1.1.0", "module": "perplexity", "file_name": "perplexity"},
        ]

    async def test_build_model(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        model = component.build_model()
        assert model is not None
        assert model.model == default_kwargs["model_name"]
        assert model.temperature == default_kwargs["temperature"]
        assert model.pplx_api_key == default_kwargs["api_key"]
        assert model.max_output_tokens == default_kwargs["max_output_tokens"]
        assert model.top_k == default_kwargs["top_k"]
        assert model.top_p == default_kwargs["top_p"]
        assert model.n == default_kwargs["n"]

    async def test_perplexity_component_latest(self, component_class, default_kwargs):
        result = await component_class(**default_kwargs).run()
        assert result is not None

import pytest
from langflow.components.models import AnthropicModelComponent

from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestAnthropicModelComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return AnthropicModelComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "api_key": "test_api_key",
            "model_name": "claude-v1",
            "max_tokens": 4096,
            "temperature": 0.1,
            "base_url": "https://api.anthropic.com",
            "tool_model_enabled": False,
            "prefill": "Hello, how can I assist you today?",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "anthropic", "file_name": "AnthropicModel"},
            {"version": "1.1.0", "module": "anthropic", "file_name": "anthropic_model"},
        ]

    async def test_build_model(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        model = component.build_model()
        assert model is not None

    async def test_get_models(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        models = component.get_models()
        assert isinstance(models, list)
        assert len(models) > 0

    async def test_update_build_config(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        build_config = {}
        updated_config = component.update_build_config(build_config, "test_api_key", "api_key")
        assert "model_name" in updated_config
        assert "options" in updated_config["model_name"]

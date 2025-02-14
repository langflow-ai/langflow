import pytest

from langflow.components.models import SambaNovaComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestSambaNovaComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return SambaNovaComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "sambanova_url": "https://api.sambanova.ai/v1/chat/completions",
            "model_name": "sambanova_model_1",
            "sambanova_api_key": "SAMBANOVA_API_KEY",
            "max_tokens": 4096,
            "temperature": 0.1,
            "_session_id": "123",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "sambanova", "file_name": "SambaNova"},
            {"version": "1.1.0", "module": "sambanova", "file_name": "sambanova"},
        ]

    async def test_build_model(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        model = component.build_model()
        assert model is not None
        assert model.model == default_kwargs["model_name"]
        assert model.max_tokens == default_kwargs["max_tokens"]
        assert model.temperature == default_kwargs["temperature"]
        assert model.sambanova_url == default_kwargs["sambanova_url"]

    async def test_component_latest_version(self, component_class, default_kwargs):
        result = await component_class(**default_kwargs).run()
        assert result is not None

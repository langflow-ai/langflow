import pytest

from langflow.components.embeddings import MistralAIEmbeddingsComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestMistralAIEmbeddingsComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return MistralAIEmbeddingsComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "mistral_api_key": "test_api_key",
            "model": "mistral-embed",
            "max_concurrent_requests": 64,
            "max_retries": 5,
            "timeout": 120,
            "endpoint": "https://api.mistral.ai/v1/",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "embeddings", "file_name": "MistralAIEmbeddings"},
        ]

    def test_build_embeddings_with_valid_api_key(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        embeddings = component.build_embeddings()
        assert embeddings is not None
        assert embeddings.api_key == "test_api_key"
        assert embeddings.model == "mistral-embed"

    def test_build_embeddings_without_api_key(self, component_class):
        component = component_class(mistral_api_key="", model="mistral-embed")
        with pytest.raises(ValueError, match="Mistral API Key is required"):
            component.build_embeddings()

    async def test_latest_version(self, component_class, default_kwargs):
        component_instance = await self.component_setup(component_class, default_kwargs)
        result = await component_instance.run()
        assert result is not None, "Component returned None for the latest version."

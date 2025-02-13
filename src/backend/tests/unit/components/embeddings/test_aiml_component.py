import pytest

from langflow.components.embeddings import AIMLEmbeddingsComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestAIMLEmbeddingsComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return AIMLEmbeddingsComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "model_name": "text-embedding-ada-002",
            "aiml_api_key": "test_api_key",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "embeddings", "file_name": "AIMLEmbeddings"},
        ]

    async def test_build_embeddings(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        embeddings = component.build_embeddings()
        assert embeddings is not None
        assert embeddings.api_key == default_kwargs["aiml_api_key"]
        assert embeddings.model == default_kwargs["model_name"]

    async def test_component_latest_version(self, component_class, default_kwargs):
        result = await component_class(**default_kwargs).run()
        assert result is not None

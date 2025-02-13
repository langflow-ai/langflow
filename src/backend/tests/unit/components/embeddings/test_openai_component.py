import pytest
from langflow.components.embeddings import OpenAIEmbeddingsComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestOpenAIEmbeddingsComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return OpenAIEmbeddingsComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "client": "test_client",
            "deployment": "test_deployment",
            "openai_api_key": "test_api_key",
            "model": "text-embedding-3-small",
            "dimensions": 512,
            "chunk_size": 1000,
            "embedding_ctx_length": 1536,
            "max_retries": 3,
            "request_timeout": 30.0,
            "show_progress_bar": True,
            "skip_empty": False,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "embeddings", "file_name": "OpenAIEmbeddings"},
        ]

    async def test_build_embeddings(self, component_class, default_kwargs):
        # Arrange
        component = component_class(**default_kwargs)

        # Act
        embeddings = component.build_embeddings()

        # Assert
        assert embeddings is not None
        assert embeddings.client == default_kwargs["client"]
        assert embeddings.model == default_kwargs["model"]
        assert embeddings.dimensions == default_kwargs["dimensions"]
        assert embeddings.chunk_size == default_kwargs["chunk_size"]

    async def test_component_latest_version(self, component_class, default_kwargs):
        # Arrange
        component = await self.component_setup(component_class, default_kwargs)

        # Act
        result = await component.run()

        # Assert
        assert result is not None

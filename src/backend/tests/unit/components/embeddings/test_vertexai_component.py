import pytest
from langflow.components.embeddings import VertexAIEmbeddingsComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestVertexAIEmbeddingsComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return VertexAIEmbeddingsComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "credentials": "path/to/credentials.json",
            "location": "us-central1",
            "project": "test-project",
            "max_output_tokens": 100,
            "max_retries": 1,
            "model_name": "textembedding-gecko",
            "n": 1,
            "request_parallelism": 5,
            "stop_sequences": [],
            "streaming": False,
            "temperature": 0.0,
            "top_k": 50,
            "top_p": 0.95,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return []

    async def test_build_embeddings(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = await component.build_embeddings()
        assert result is not None, "Embeddings should not be None."
        assert hasattr(result, "embeddings"), "Result should have 'embeddings' attribute."

    def test_component_initialization(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        assert component.credentials == default_kwargs["credentials"]
        assert component.location == default_kwargs["location"]
        assert component.project == default_kwargs["project"]
        assert component.model_name == default_kwargs["model_name"]

import pytest

from langflow.components.embeddings import CohereEmbeddingsComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestCohereEmbeddingsComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return CohereEmbeddingsComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "cohere_api_key": "test_api_key",
            "model": "embed-english-v2.0",
            "truncate": "test_truncate",
            "max_retries": 3,
            "user_agent": "langchain",
            "request_timeout": 5.0,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return []

    async def test_build_embeddings(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        embeddings = component.build_embeddings()
        assert embeddings is not None
        assert embeddings.cohere_api_key == default_kwargs["cohere_api_key"]
        assert embeddings.model == default_kwargs["model"]
        assert embeddings.truncate == default_kwargs["truncate"]
        assert embeddings.max_retries == default_kwargs["max_retries"]
        assert embeddings.user_agent == default_kwargs["user_agent"]
        assert embeddings.request_timeout == default_kwargs["request_timeout"]

    async def test_component_latest_version(self, component_class, default_kwargs):
        component_instance = await self.component_setup(component_class, default_kwargs)
        result = await component_instance.run()
        assert result is not None

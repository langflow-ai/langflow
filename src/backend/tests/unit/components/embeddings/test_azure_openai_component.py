import pytest
from langflow.components.embeddings import AzureOpenAIEmbeddingsComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestAzureOpenAIEmbeddingsComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return AzureOpenAIEmbeddingsComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "model": "text-embedding-ada-002",
            "azure_endpoint": "https://example-resource.azure.openai.com/",
            "azure_deployment": "my-deployment",
            "api_version": "2023-08-01-preview",
            "api_key": "my-secret-api-key",
            "dimensions": 1536,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "embeddings", "file_name": "AzureOpenAIEmbeddings"},
        ]

    async def test_build_embeddings(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = await component.build_embeddings()
        assert result is not None
        assert isinstance(result, list)  # Assuming embeddings are returned as a list

    def test_component_latest_version(self, component_class, default_kwargs):
        result = component_class(**default_kwargs)()
        assert result is not None

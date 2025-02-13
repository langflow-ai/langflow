import pytest

from langflow.components.embeddings import CloudflareWorkersAIEmbeddingsComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestCloudflareWorkersAIEmbeddingsComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return CloudflareWorkersAIEmbeddingsComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "account_id": "your_account_id",
            "api_token": "your_api_token",
            "model_name": "@cf/baai/bge-base-en-v1.5",
            "strip_new_lines": True,
            "batch_size": 50,
            "api_base_url": "https://api.cloudflare.com/client/v4/accounts",
            "headers": {},
        }

    @pytest.fixture
    def file_names_mapping(self):
        return []

    async def test_build_embeddings(self, component_class, default_kwargs):
        component_instance = await self.component_setup(component_class, default_kwargs)
        result = await component_instance.build_embeddings()
        assert result is not None, "Embeddings should not be None."

    async def test_invalid_api_token(self, component_class):
        invalid_kwargs = {
            "account_id": "your_account_id",
            "api_token": "invalid_api_token",
            "model_name": "@cf/baai/bge-base-en-v1.5",
            "strip_new_lines": True,
            "batch_size": 50,
            "api_base_url": "https://api.cloudflare.com/client/v4/accounts",
            "headers": {},
        }
        component_instance = await self.component_setup(component_class, invalid_kwargs)
        with pytest.raises(ValueError, match="Could not connect to CloudflareWorkersAIEmbeddings API"):
            await component_instance.build_embeddings()

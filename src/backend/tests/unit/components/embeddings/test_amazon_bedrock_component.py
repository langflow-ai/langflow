import pytest

from langflow.components.embeddings import AmazonBedrockEmbeddingsComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestAmazonBedrockEmbeddingsComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return AmazonBedrockEmbeddingsComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "model_id": "amazon.titan-embed-text-v1",
            "aws_access_key_id": "test_access_key",
            "aws_secret_access_key": "test_secret_key",
            "aws_session_token": "test_session_token",
            "credentials_profile_name": "default",
            "region_name": "us-east-1",
            "endpoint_url": "https://example.com",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "aws", "file_name": "AmazonBedrockEmbeddings"},
        ]

    async def test_build_embeddings(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = await component.build_embeddings()
        assert result is not None, "Embeddings should not be None."

    def test_component_latest_version(self, component_class, default_kwargs):
        result = component_class(**default_kwargs)()
        assert result is not None

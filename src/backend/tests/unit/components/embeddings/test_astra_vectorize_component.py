import pytest
from langflow.components.embeddings import AstraVectorizeComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestAstraVectorizeComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return AstraVectorizeComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "provider": "OpenAI",
            "model_name": "text-embedding-ada-002",
            "api_key_name": "my_api_key",
            "authentication": {"key": "value"},
            "provider_api_key": "provider_secret_key",
            "model_parameters": {"param1": "value1"},
        }

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_build_options(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        options = component.build_options()

        assert options["collection_vector_service_options"]["provider"] == "openai"
        assert options["collection_vector_service_options"]["modelName"] == "text-embedding-ada-002"
        assert options["collection_vector_service_options"]["authentication"]["providerKey"] == "my_api_key"
        assert options["collection_embedding_api_key"] == "provider_secret_key"

    def test_missing_api_key_name(self, component_class):
        component = component_class(provider="Azure OpenAI", model_name="text-embedding-3-small")
        options = component.build_options()

        assert "providerKey" not in options["collection_vector_service_options"]["authentication"]

    def test_empty_model_parameters(self, component_class):
        component = component_class(
            provider="Hugging Face - Serverless",
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            model_parameters={},
        )
        options = component.build_options()

        assert options["collection_vector_service_options"]["parameters"] == {}

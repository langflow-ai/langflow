import pytest
from langflow.components.embeddings import GoogleGenerativeAIEmbeddingsComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestGoogleGenerativeAIEmbeddingsComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return GoogleGenerativeAIEmbeddingsComponent

    @pytest.fixture
    def default_kwargs(self):
        return {"api_key": "test_api_key", "model_name": "models/text-embedding-004"}

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "embeddings", "file_name": "GoogleGenerativeAIEmbeddings"},
        ]

    def test_build_embeddings_without_api_key(self, component_class):
        component = component_class(api_key="", model_name="models/text-embedding-004")
        with pytest.raises(ValueError, match="API Key is required"):
            component.build_embeddings()

    def test_build_embeddings_with_valid_input(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = component.build_embeddings()
        assert result is not None

    def test_embed_documents_with_invalid_dimension(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        with pytest.raises(ValueError, match="Output dimensionality must be at least 1"):
            component.build_embeddings().embed_documents(["text"], output_dimensionality=0)

        with pytest.raises(ValueError, match="Output dimensionality cannot exceed 768"):
            component.build_embeddings().embed_documents(["text"], output_dimensionality=800)

    def test_embed_query_with_invalid_dimension(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        with pytest.raises(ValueError, match="Output dimensionality must be at least 1"):
            component.build_embeddings().embed_query("text", output_dimensionality=0)

        with pytest.raises(ValueError, match="Output dimensionality cannot exceed 768"):
            component.build_embeddings().embed_query("text", output_dimensionality=800)

    def test_component_versions(self, version, default_kwargs, file_names_mapping):
        super().test_component_versions(version, default_kwargs, file_names_mapping)

"""Tests for OpenSearch Multi-Model Multi-Embedding Vector Store Component."""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.embeddings import Embeddings
from lfx.base.embeddings.embeddings_class import EmbeddingsWithModels
from lfx.components.elastic.opensearch_multimodal import (
    OpenSearchVectorStoreComponentMultimodalMultiEmbedding,
    get_embedding_field_name,
    normalize_model_name,
)
from lfx.schema.data import Data

from tests.base import ComponentTestBaseWithoutClient, VersionComponentMapping


# Fixture: Simple embeddings for testing
class MockEmbeddings(Embeddings):
    """Mock embeddings class for testing purposes."""

    def __init__(self, model: str = "test-model", dimension: int = 384):
        """Initialize test embeddings.

        Args:
            model: Model name identifier
            dimension: Embedding dimension
        """
        super().__init__()
        self.model = model
        self.dimension = dimension

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Return simple fixed-dimension embeddings for documents."""
        return [[0.1 * (i + 1)] * self.dimension for i in range(len(texts))]

    def embed_query(self, text: str) -> list[float]:
        """Return simple fixed-dimension embedding for query."""
        # mocking the embeddings length to be the length of the text
        return [0.5] * (self.dimension * len(text))

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        """Return async embeddings for documents."""
        return self.embed_documents(texts)

    async def aembed_query(self, text: str) -> list[float]:
        """Return async embedding for query."""
        return self.embed_query(text)


@pytest.fixture
def embedding_small():
    """Create a small dimension embedding for testing."""
    return MockEmbeddings(model="text-embedding-small", dimension=384)


@pytest.fixture
def embedding_large():
    """Create a large dimension embedding for testing."""
    return MockEmbeddings(model="text-embedding-large", dimension=1536)


@pytest.fixture
def embedding_bge():
    """Create a BGE embedding for testing."""
    return MockEmbeddings(model="bge-large:latest", dimension=1024)


@pytest.fixture
def embeddings_with_models_openai(embedding_small, embedding_large):
    """Create EmbeddingsWithModels for OpenAI with multiple models."""
    return EmbeddingsWithModels(
        embeddings=embedding_small,
        available_models={
            "text-embedding-3-small": embedding_small,
            "text-embedding-3-large": embedding_large,
        },
    )


@pytest.fixture
def embeddings_with_models_ollama(embedding_bge):
    """Create EmbeddingsWithModels for Ollama with multiple models."""
    embedding_qwen = MockEmbeddings(model="qwen3-embedding:4b", dimension=512)
    return EmbeddingsWithModels(
        embeddings=embedding_bge,
        available_models={
            "bge-large:latest": embedding_bge,
            "qwen3-embedding:4b": embedding_qwen,
        },
    )


@pytest.fixture
def sample_documents():
    """Create sample documents for testing."""
    return [
        Data(text="Python is a programming language", data={"text": "Python is a programming language"}),
        Data(text="Machine learning uses neural networks", data={"text": "Machine learning uses neural networks"}),
        Data(text="OpenSearch is a search engine", data={"text": "OpenSearch is a search engine"}),
    ]


@pytest.fixture
def mock_opensearch_client():
    """Create a mock OpenSearch client."""
    client = MagicMock()

    # Mock index operations
    client.indices.exists.return_value = False
    client.indices.create.return_value = {"acknowledged": True}
    client.indices.get_mapping.return_value = {
        "test_index": {
            "mappings": {
                "properties": {
                    "chunk": {"type": "text"},
                    "chunk_embedding_text_embedding_3_small": {
                        "type": "knn_vector",
                        "dimension": 384,
                    },
                    "chunk_embedding_text_embedding_3_large": {
                        "type": "knn_vector",
                        "dimension": 1536,
                    },
                }
            }
        }
    }

    # Mock bulk operations
    client.bulk.return_value = {"errors": False, "items": []}

    # Mock search operations
    client.search.return_value = {
        "hits": {
            "total": {"value": 2},
            "hits": [
                {
                    "_source": {"chunk": "Python is a programming language"},
                    "_score": 0.95,
                },
                {
                    "_source": {"chunk": "Machine learning uses neural networks"},
                    "_score": 0.85,
                },
            ],
        }
    }

    return client


class TestNormalizationFunctions:
    """Test model name normalization functions."""

    def test_normalize_model_name_basic(self):
        """Test basic model name normalization."""
        assert normalize_model_name("text-embedding-3-small") == "text_embedding_3_small"

    def test_normalize_model_name_with_colon(self):
        """Test normalization with colon separator."""
        assert normalize_model_name("bge-large:latest") == "bge_large_latest"

    def test_normalize_model_name_with_slash(self):
        """Test normalization with slash separator."""
        assert normalize_model_name("openai/text-ada-002") == "openai_text_ada_002"

    def test_normalize_model_name_with_dot(self):
        """Test normalization with dot separator."""
        assert normalize_model_name("model.v1.0") == "model_v1_0"

    def test_normalize_model_name_complex(self):
        """Test normalization with multiple special characters."""
        assert normalize_model_name("text-embedding:v1.0/large") == "text_embedding_v1_0_large"

    def test_normalize_model_name_duplicate_underscores(self):
        """Test that duplicate underscores are removed."""
        assert normalize_model_name("text--embedding__3") == "text_embedding_3"

    def test_normalize_model_name_strips_underscores(self):
        """Test that leading/trailing underscores are removed."""
        assert normalize_model_name("-text-embedding-") == "text_embedding"

    def test_get_embedding_field_name(self):
        """Test embedding field name generation."""
        field_name = get_embedding_field_name("text-embedding-3-small")
        assert field_name == "chunk_embedding_text_embedding_3_small"

    def test_get_embedding_field_name_with_special_chars(self):
        """Test field name generation with special characters."""
        field_name = get_embedding_field_name("bge-large:latest")
        assert field_name == "chunk_embedding_bge_large_latest"


class TestOpenSearchMultimodalComponent(ComponentTestBaseWithoutClient):
    """Test suite for OpenSearch Multi-Model Multi-Embedding component."""

    @pytest.fixture
    def component_class(self) -> type[Any]:
        """Return the component class to test."""
        return OpenSearchVectorStoreComponentMultimodalMultiEmbedding

    @pytest.fixture
    def default_kwargs(self, embedding_small) -> dict[str, Any]:
        """Return the default kwargs for the component."""
        return {
            "opensearch_url": "http://localhost:9200",
            "index_name": "test_index",
            "embedding": embedding_small,
            "auth_mode": "No Authentication",
            "number_of_results": 5,
        }

    @pytest.fixture
    def file_names_mapping(self) -> list[VersionComponentMapping]:
        """Return the file names mapping for different versions."""
        # This is a new component, so no version history yet
        return []

    def test_component_initialization(self, component_class):
        """Test that component initializes correctly."""
        component = component_class()
        assert component.display_name == "OpenSearch (Multi-Model Multi-Embedding)"
        assert component.icon == "OpenSearch"
        assert component.description is not None

    def test_build_with_single_embedding(
        self,
        component_class,
        default_kwargs,
    ):
        """Test building component with a single embedding."""
        component = component_class().set(**default_kwargs)

        # Verify attributes are set correctly
        assert component.embedding is not None
        assert component.opensearch_url == "http://localhost:9200"
        assert component.index_name == "test_index"

    def test_build_with_embeddings_with_models(
        self,
        component_class,
        embeddings_with_models_openai,
    ):
        """Test building component with EmbeddingsWithModels."""
        component = component_class().set(
            opensearch_url="http://localhost:9200",
            index_name="test_index",
            embedding=embeddings_with_models_openai,
            auth_mode="No Authentication",
            number_of_results=5,
        )

        # Verify EmbeddingsWithModels is properly set
        assert isinstance(component.embedding, EmbeddingsWithModels)
        assert len(component.embedding.available_models) == 2
        assert "text-embedding-3-small" in component.embedding.available_models
        assert "text-embedding-3-large" in component.embedding.available_models

    def test_build_with_multiple_embeddings(
        self,
        component_class,
        embeddings_with_models_openai,
        embeddings_with_models_ollama,
    ):
        """Test building component with multiple EmbeddingsWithModels."""
        component = component_class().set(
            opensearch_url="http://localhost:9200",
            index_name="test_index",
            embedding=[embeddings_with_models_openai, embeddings_with_models_ollama],
            auth_mode="No Authentication",
            number_of_results=5,
        )

        # Note: set() with a list keeps only the last item, so we verify the embedding is valid
        # In actual usage, the component can handle lists during processing
        assert component.embedding is not None
        assert isinstance(component.embedding, EmbeddingsWithModels)

    def test_get_embedding_model_name_with_deployment(self, component_class):
        """Test getting embedding model name with deployment attribute."""
        component = component_class()
        embedding = MockEmbeddings(model="test-model", dimension=384)
        embedding.deployment = "deployment-name"

        model_name = component._get_embedding_model_name(embedding)
        assert model_name == "deployment-name"

    def test_get_embedding_model_name_with_model(self, component_class):
        """Test getting embedding model name with model attribute."""
        component = component_class()
        embedding = MockEmbeddings(model="test-model", dimension=384)

        model_name = component._get_embedding_model_name(embedding)
        assert model_name == "test-model"

    def test_get_embedding_model_name_with_model_name(self, component_class):
        """Test getting embedding model name with model_name attribute."""
        component = component_class()
        embedding = MockEmbeddings(model="test-model", dimension=384)
        embedding.model_name = "model-name-attr"

        model_name = component._get_embedding_model_name(embedding)
        # model_name has lower priority than model
        assert model_name in ["model-name-attr", "test-model"]

    def test_get_embedding_model_name_none(self, component_class):
        """Test getting embedding model name when no identifying attributes exist raises ValueError."""
        component = component_class()
        embedding = MockEmbeddings()
        # Remove model attribute
        del embedding.model

        # Should raise ValueError when no model name can be determined
        with pytest.raises(ValueError, match="Could not determine embedding model name"):
            component._get_embedding_model_name(embedding)

    @patch("lfx.components.elastic.opensearch_multimodal.OpenSearch")
    def test_detect_available_models_from_index(
        self,
        mock_opensearch_class,
        component_class,
        default_kwargs,
        mock_opensearch_client,
    ):
        """Test detecting available models from index mappings."""
        # Set up mock search response with aggregations
        mock_opensearch_client.search.return_value = {
            "aggregations": {
                "embedding_models": {
                    "buckets": [
                        {"key": "text-embedding-3-small", "doc_count": 10},
                        {"key": "text-embedding-3-large", "doc_count": 5},
                    ]
                }
            }
        }
        mock_opensearch_class.return_value = mock_opensearch_client

        component = component_class().set(**default_kwargs)

        # Call the method directly with the mocked client
        models = component._detect_available_models(mock_opensearch_client)

        # Verify models are detected from the aggregations
        assert "text-embedding-3-small" in models
        assert "text-embedding-3-large" in models
        assert len(models) == 2

    def test_authentication_basic(self, component_class):
        """Test component configuration with basic authentication."""
        component = component_class().set(
            opensearch_url="http://localhost:9200",
            index_name="test_index",
            embedding=MockEmbeddings(),
            auth_mode="Basic Authentication",
            username="test_user",
            password="test_password",  # pragma: allowlist secret  # noqa: S106
        )

        # Verify auth settings
        assert component.auth_mode == "Basic Authentication"
        assert component.username == "test_user"
        assert component.password == "test_password"  # pragma: allowlist secret  # noqa: S105

    def test_authentication_jwt(self, component_class):
        """Test component configuration with JWT authentication."""
        component = component_class().set(
            opensearch_url="http://localhost:9200",
            index_name="test_index",
            embedding=MockEmbeddings(),
            auth_mode="JWT Token",
            jwt_token="test_jwt_token",  # pragma: allowlist secret  # noqa: S106
        )

        # Verify JWT settings
        assert component.auth_mode == "JWT Token"
        assert component.jwt_token == "test_jwt_token"  # pragma: allowlist secret  # noqa: S105

    def test_authentication_bearer(self, component_class):
        """Test component configuration with Bearer token authentication."""
        component = component_class().set(
            opensearch_url="http://localhost:9200",
            index_name="test_index",
            embedding=MockEmbeddings(),
            auth_mode="Bearer Token",
            bearer_token="test_bearer_token",  # pragma: allowlist secret  # noqa: S106
        )

        # Verify Bearer settings
        assert component.auth_mode == "Bearer Token"
        assert component.bearer_token == "test_bearer_token"  # pragma: allowlist secret  # noqa: S105

    async def test_update_build_config_auth_basic(self, component_class):
        """Test update_build_config with basic authentication."""
        component = component_class()
        build_config = {
            "username": {"required": False, "show": False},
            "password": {"required": False, "show": False},
            "jwt_token": {"required": False, "show": False},
            "bearer_token": {"required": False, "show": False},
            "bearer_prefix": {"required": False, "show": False},
            "jwt_header": {"required": False, "show": False},
        }

        updated_config = await component.update_build_config(build_config, "basic", "auth_mode")

        # Verify basic auth fields are visible and required
        assert updated_config["username"]["show"] is True
        assert updated_config["username"]["required"] is True
        assert updated_config["password"]["show"] is True
        assert updated_config["password"]["required"] is True
        # JWT fields should be hidden
        assert updated_config["jwt_token"]["show"] is False
        assert updated_config["jwt_header"]["show"] is False

    async def test_update_build_config_auth_jwt(self, component_class):
        """Test update_build_config with JWT authentication."""
        component = component_class()
        build_config = {
            "username": {"required": False, "show": False},
            "password": {"required": False, "show": False},
            "jwt_token": {"required": False, "show": False},
            "bearer_token": {"required": False, "show": False},
            "bearer_prefix": {"required": False, "show": False},
            "jwt_header": {"required": False, "show": False},
        }

        updated_config = await component.update_build_config(build_config, "jwt", "auth_mode")

        # Verify JWT fields are visible and required
        assert updated_config["jwt_token"]["show"] is True
        assert updated_config["jwt_token"]["required"] is True
        assert updated_config["jwt_header"]["show"] is True
        assert updated_config["jwt_header"]["required"] is True
        assert updated_config["bearer_prefix"]["show"] is True
        assert updated_config["bearer_prefix"]["required"] is False
        # Basic auth fields should be hidden
        assert updated_config["username"]["show"] is False
        assert updated_config["password"]["show"] is False

    async def test_update_build_config_auth_no_auth(self, component_class):
        """Test update_build_config with no authentication (all fields hidden)."""
        component = component_class()
        build_config = {
            "username": {"required": True, "show": True},
            "password": {"required": True, "show": True},
            "jwt_token": {"required": True, "show": True},
            "bearer_token": {"required": False, "show": False},
            "bearer_prefix": {"required": False, "show": False},
            "jwt_header": {"required": True, "show": True},
        }

        updated_config = await component.update_build_config(build_config, "none", "auth_mode")

        # When mode is not "basic" or "jwt", all auth fields should be hidden
        assert updated_config["username"]["show"] is False
        assert updated_config["password"]["show"] is False
        assert updated_config["jwt_token"]["show"] is False
        assert updated_config["jwt_header"]["show"] is False
        assert updated_config["bearer_prefix"]["show"] is False


class TestOpenSearchMultimodalIntegration:
    """Integration tests for OpenSearch multimodal component."""

    def test_multi_embedding_configuration(self, embeddings_with_models_openai, embeddings_with_models_ollama):
        """Test that multiple embeddings are properly configured."""
        component = OpenSearchVectorStoreComponentMultimodalMultiEmbedding()
        component.set_attributes(
            {
                "opensearch_url": "http://localhost:9200",
                "index_name": "test_index",
                "embedding": [embeddings_with_models_openai, embeddings_with_models_ollama],
                "auth_mode": "No Authentication",
                "number_of_results": 5,
            }
        )

        assert isinstance(component.embedding, list)
        assert len(component.embedding) == 2

        # Verify all available models
        all_models = {}
        for emb_wrapper in component.embedding:
            if isinstance(emb_wrapper, EmbeddingsWithModels):
                all_models.update(emb_wrapper.available_models)

        # Should have models from both OpenAI and Ollama
        assert len(all_models) >= 4  # 2 from OpenAI + 2 from Ollama

    def test_field_mapping_generation(self):
        """Test that field mappings are correctly generated for multiple models."""
        # Verify that field names would be generated correctly
        expected_fields = [
            "chunk_embedding_text_embedding_3_small",
            "chunk_embedding_text_embedding_3_large",
            "chunk_embedding_bge_large_latest",
            "chunk_embedding_qwen3_embedding_4b",
        ]

        for model_name in [
            "text-embedding-3-small",
            "text-embedding-3-large",
            "bge-large:latest",
            "qwen3-embedding:4b",
        ]:
            field_name = get_embedding_field_name(model_name)
            assert field_name in expected_fields

    def test_embedding_dimension_consistency(self, embeddings_with_models_openai, embeddings_with_models_ollama):
        """Test that each model maintains its own dimension."""
        embeddings_list = [embeddings_with_models_openai, embeddings_with_models_ollama]

        for emb_wrapper in embeddings_list:
            if isinstance(emb_wrapper, EmbeddingsWithModels):
                for model_instance in emb_wrapper.available_models.values():
                    # Each model should have consistent dimensions
                    vec1 = model_instance.embed_query("test1")
                    vec2 = model_instance.embed_query("test2")
                    assert len(vec1) == len(vec2)

    async def test_async_embedding_generation(self, embeddings_with_models_openai, embeddings_with_models_ollama):
        """Test async embedding generation for multiple models."""
        embeddings_list = [embeddings_with_models_openai, embeddings_with_models_ollama]

        for emb_wrapper in embeddings_list:
            if isinstance(emb_wrapper, EmbeddingsWithModels):
                for model_instance in emb_wrapper.available_models.values():
                    # Test async embedding
                    vec = await model_instance.aembed_query("test query")
                    assert len(vec) > 0
                    assert all(isinstance(v, float) for v in vec)

    def test_model_name_retrieval(self, embeddings_with_models_openai, embeddings_with_models_ollama):
        """Test retrieving model names from embedding instances."""
        component = OpenSearchVectorStoreComponentMultimodalMultiEmbedding()
        embeddings_list = [embeddings_with_models_openai, embeddings_with_models_ollama]

        model_names = []
        for emb_wrapper in embeddings_list:
            if isinstance(emb_wrapper, EmbeddingsWithModels):
                # Get primary model name
                primary_name = component._get_embedding_model_name(emb_wrapper.embeddings)
                if primary_name:
                    model_names.append(primary_name)

                # Get all available model names
                model_names.extend(emb_wrapper.available_models.keys())

        # Should have multiple distinct model names
        assert len(set(model_names)) >= 4

    def test_empty_available_models(self):
        """Test component with EmbeddingsWithModels that has empty available_models."""
        embedding = MockEmbeddings(model="test-model", dimension=384)
        wrapper = EmbeddingsWithModels(embeddings=embedding, available_models={})

        component = OpenSearchVectorStoreComponentMultimodalMultiEmbedding()
        component.set_attributes(
            {
                "opensearch_url": "http://localhost:9200",
                "index_name": "test_index",
                "embedding": wrapper,
                "auth_mode": "No Authentication",
            }
        )

        # Should still work with empty available_models
        assert isinstance(component.embedding, EmbeddingsWithModels)
        assert len(component.embedding.available_models) == 0

    def test_mixed_embedding_types(self):
        """Test component with both EmbeddingsWithModels and regular Embeddings."""
        regular_embedding = MockEmbeddings(model="regular-model", dimension=384)
        wrapped_embedding = EmbeddingsWithModels(
            embeddings=MockEmbeddings(model="wrapped-model", dimension=512),
            available_models={"model-a": MockEmbeddings(model="model-a", dimension=768)},
        )

        component = OpenSearchVectorStoreComponentMultimodalMultiEmbedding()
        component.set_attributes(
            {
                "opensearch_url": "http://localhost:9200",
                "index_name": "test_index",
                "embedding": [regular_embedding, wrapped_embedding],
                "auth_mode": "No Authentication",
            }
        )

        # Should handle mixed types
        assert isinstance(component.embedding, list)
        assert len(component.embedding) == 2

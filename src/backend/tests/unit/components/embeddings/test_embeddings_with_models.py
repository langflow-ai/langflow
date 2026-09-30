"""Tests for EmbeddingsWithModels class."""

from typing import Any

import pytest
from langchain_core.embeddings import Embeddings
from lfx.base.embeddings.embeddings_class import EmbeddingsWithModels


# Test fixture: Create a simple mock embeddings class for testing
class SimpleEmbeddings(Embeddings):
    """Simple embeddings class for testing purposes."""

    def __init__(self, model: str = "test-model", dimension: int = 384):
        """Initialize simple embeddings.

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

    def embed_query(self, text: str) -> list[float]:  # noqa: ARG002
        """Return simple fixed-dimension embedding for query."""
        return [0.5] * self.dimension

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        """Return simple fixed-dimension embeddings for documents asynchronously."""
        return self.embed_documents(texts)

    async def aembed_query(self, text: str) -> list[float]:
        """Return simple fixed-dimension embedding for query asynchronously."""
        return self.embed_query(text)

    def custom_method(self) -> str:
        """Custom method to test __getattr__ delegation."""
        return f"custom method from {self.model}"


@pytest.fixture
def primary_embedding():
    """Create a primary embedding instance for testing."""
    return SimpleEmbeddings(model="primary-model", dimension=384)


@pytest.fixture
def secondary_embedding():
    """Create a secondary embedding instance for testing."""
    return SimpleEmbeddings(model="secondary-model", dimension=512)


@pytest.fixture
def tertiary_embedding():
    """Create a tertiary embedding instance for testing."""
    return SimpleEmbeddings(model="tertiary-model", dimension=768)


@pytest.fixture
def available_models_dict(secondary_embedding, tertiary_embedding):
    """Create a dictionary of available models for testing."""
    return {
        "model-a": secondary_embedding,
        "model-b": tertiary_embedding,
    }


@pytest.fixture
def embeddings_with_models(primary_embedding, available_models_dict):
    """Create EmbeddingsWithModels instance for testing."""
    return EmbeddingsWithModels(
        embeddings=primary_embedding,
        available_models=available_models_dict,
    )


class TestEmbeddingsWithModelsInitialization:
    """Test initialization of EmbeddingsWithModels."""

    def test_init_with_available_models(self, primary_embedding, available_models_dict):
        """Test initialization with available models dict."""
        wrapper = EmbeddingsWithModels(
            embeddings=primary_embedding,
            available_models=available_models_dict,
        )

        assert wrapper.embeddings is primary_embedding
        assert wrapper.available_models == available_models_dict
        assert len(wrapper.available_models) == 2
        assert "model-a" in wrapper.available_models
        assert "model-b" in wrapper.available_models

    def test_init_without_available_models(self, primary_embedding):
        """Test initialization without available models (defaults to empty dict)."""
        wrapper = EmbeddingsWithModels(embeddings=primary_embedding)

        assert wrapper.embeddings is primary_embedding
        assert wrapper.available_models == {}
        assert isinstance(wrapper.available_models, dict)

    def test_init_with_none_available_models(self, primary_embedding):
        """Test initialization with None for available_models."""
        wrapper = EmbeddingsWithModels(embeddings=primary_embedding, available_models=None)

        assert wrapper.embeddings is primary_embedding
        assert wrapper.available_models == {}

    def test_inherits_from_embeddings(self, embeddings_with_models):
        """Test that EmbeddingsWithModels inherits from Embeddings."""
        assert isinstance(embeddings_with_models, Embeddings)


class TestEmbeddingsWithModelsEmbedMethods:
    """Test embedding methods of EmbeddingsWithModels."""

    def test_embed_documents(self, embeddings_with_models):
        """Test embed_documents delegates to underlying embeddings."""
        texts = ["hello", "world", "test"]
        result = embeddings_with_models.embed_documents(texts)

        assert len(result) == 3
        assert len(result[0]) == 384  # primary model dimension
        assert pytest.approx(result[0][0]) == 0.1
        assert pytest.approx(result[1][0]) == 0.2
        assert pytest.approx(result[2][0]) == 0.3

    def test_embed_query(self, embeddings_with_models):
        """Test embed_query delegates to underlying embeddings."""
        text = "test query"
        result = embeddings_with_models.embed_query(text)

        assert len(result) == 384  # primary model dimension
        assert result[0] == 0.5

    async def test_aembed_documents(self, embeddings_with_models):
        """Test async embed_documents delegates to underlying embeddings."""
        texts = ["hello", "world", "test"]
        result = await embeddings_with_models.aembed_documents(texts)

        assert len(result) == 3
        assert len(result[0]) == 384
        assert result[0][0] == 0.1

    async def test_aembed_query(self, embeddings_with_models):
        """Test async embed_query delegates to underlying embeddings."""
        text = "test query"
        result = await embeddings_with_models.aembed_query(text)

        assert len(result) == 384
        assert result[0] == 0.5


class TestEmbeddingsWithModelsAvailableModels:
    """Test available_models functionality."""

    def test_available_models_dict_access(self, embeddings_with_models):
        """Test that available_models dict can be accessed."""
        available = embeddings_with_models.available_models

        assert isinstance(available, dict)
        assert len(available) == 2
        assert "model-a" in available
        assert "model-b" in available

    def test_available_models_instances(self, embeddings_with_models, secondary_embedding, tertiary_embedding):
        """Test that available_models contains correct embedding instances."""
        model_a = embeddings_with_models.available_models["model-a"]
        model_b = embeddings_with_models.available_models["model-b"]

        assert model_a is secondary_embedding
        assert model_b is tertiary_embedding
        assert model_a.model == "secondary-model"
        assert model_b.model == "tertiary-model"

    def test_available_models_different_dimensions(self, embeddings_with_models):
        """Test that available models can have different dimensions."""
        model_a = embeddings_with_models.available_models["model-a"]
        model_b = embeddings_with_models.available_models["model-b"]

        # Test different dimensions
        vec_a = model_a.embed_query("test")
        vec_b = model_b.embed_query("test")

        assert len(vec_a) == 512  # secondary model dimension
        assert len(vec_b) == 768  # tertiary model dimension

    def test_primary_vs_available_models(self, embeddings_with_models):
        """Test that primary embedding and available models are distinct."""
        primary_vec = embeddings_with_models.embed_query("test")
        model_a_vec = embeddings_with_models.available_models["model-a"].embed_query("test")

        # Different dimensions prove they're different models
        assert len(primary_vec) == 384
        assert len(model_a_vec) == 512


class TestEmbeddingsWithModelsAttributeDelegation:
    """Test attribute delegation using __getattr__."""

    def test_getattr_delegates_to_embeddings(self, embeddings_with_models):
        """Test that __getattr__ delegates to underlying embeddings."""
        # Access model attribute through delegation
        assert embeddings_with_models.model == "primary-model"
        assert embeddings_with_models.dimension == 384

    def test_getattr_custom_method(self, embeddings_with_models):
        """Test that custom methods are accessible through delegation."""
        result = embeddings_with_models.custom_method()
        assert result == "custom method from primary-model"

    def test_getattr_nonexistent_attribute(self, embeddings_with_models):
        """Test that accessing nonexistent attributes raises AttributeError."""
        with pytest.raises(AttributeError):
            _ = embeddings_with_models.nonexistent_attribute


class TestEmbeddingsWithModelsCallable:
    """Test callable functionality using __call__."""

    def test_call_non_callable_embeddings(self, primary_embedding):
        """Test that calling non-callable embeddings raises TypeError."""
        wrapper = EmbeddingsWithModels(embeddings=primary_embedding)

        with pytest.raises(TypeError, match="'SimpleEmbeddings' object is not callable"):
            wrapper()

    def test_call_with_callable_embeddings(self):
        """Test that calling works with callable embeddings."""

        class CallableEmbeddings(Embeddings):
            def __init__(self):
                super().__init__()
                self.call_count = 0

            def embed_documents(self, texts: list[str]) -> list[list[float]]:
                return [[0.1] * 10 for _ in texts]

            def embed_query(self, text: str) -> list[float]:  # noqa: ARG002
                return [0.5] * 10

            def __call__(self, *args: Any, **kwargs: Any) -> str:
                self.call_count += 1
                return f"Called with args: {args}, kwargs: {kwargs}"

        callable_emb = CallableEmbeddings()
        wrapper = EmbeddingsWithModels(embeddings=callable_emb)

        # Test calling the wrapper
        result = wrapper("arg1", "arg2", key1="value1")

        assert result == "Called with args: ('arg1', 'arg2'), kwargs: {'key1': 'value1'}"
        assert callable_emb.call_count == 1


class TestEmbeddingsWithModelsRepr:
    """Test string representation of EmbeddingsWithModels."""

    def test_repr_with_models(self, embeddings_with_models):
        """Test __repr__ returns meaningful string representation."""
        repr_str = repr(embeddings_with_models)

        assert "EmbeddingsWithModels" in repr_str
        assert "embeddings=" in repr_str
        assert "available_models=" in repr_str

    def test_repr_without_models(self, primary_embedding):
        """Test __repr__ when no available_models are provided."""
        wrapper = EmbeddingsWithModels(embeddings=primary_embedding)
        repr_str = repr(wrapper)

        assert "EmbeddingsWithModels" in repr_str
        assert "available_models={}" in repr_str


class TestEmbeddingsWithModelsIntegration:
    """Integration tests for EmbeddingsWithModels."""

    def test_multi_model_embedding_generation(self, embeddings_with_models):
        """Test generating embeddings with multiple models."""
        query = "test query"

        # Primary model
        primary_vec = embeddings_with_models.embed_query(query)

        # Available models
        model_a_vec = embeddings_with_models.available_models["model-a"].embed_query(query)
        model_b_vec = embeddings_with_models.available_models["model-b"].embed_query(query)

        # Verify all have correct dimensions
        assert len(primary_vec) == 384
        assert len(model_a_vec) == 512
        assert len(model_b_vec) == 768

        # Verify they're all valid embeddings (non-empty, numeric)
        assert all(isinstance(v, float) for v in primary_vec)
        assert all(isinstance(v, float) for v in model_a_vec)
        assert all(isinstance(v, float) for v in model_b_vec)

    async def test_async_multi_model_embedding_generation(self, embeddings_with_models):
        """Test async embedding generation with multiple models."""
        query = "test query"

        # Primary model
        primary_vec = await embeddings_with_models.aembed_query(query)

        # Available models
        model_a_vec = await embeddings_with_models.available_models["model-a"].aembed_query(query)
        model_b_vec = await embeddings_with_models.available_models["model-b"].aembed_query(query)

        # Verify dimensions
        assert len(primary_vec) == 384
        assert len(model_a_vec) == 512
        assert len(model_b_vec) == 768

    def test_document_embedding_with_available_models(self, embeddings_with_models):
        """Test embedding documents with different models from available_models."""
        documents = ["doc1", "doc2", "doc3"]

        # Embed with different models
        primary_vecs = embeddings_with_models.embed_documents(documents)
        model_a_vecs = embeddings_with_models.available_models["model-a"].embed_documents(documents)
        model_b_vecs = embeddings_with_models.available_models["model-b"].embed_documents(documents)

        # Verify all document batches have correct length
        assert len(primary_vecs) == 3
        assert len(model_a_vecs) == 3
        assert len(model_b_vecs) == 3

        # Verify dimensions for first document
        assert len(primary_vecs[0]) == 384
        assert len(model_a_vecs[0]) == 512
        assert len(model_b_vecs[0]) == 768

    def test_empty_available_models_dict(self, primary_embedding):
        """Test that wrapper works correctly with empty available_models."""
        wrapper = EmbeddingsWithModels(embeddings=primary_embedding, available_models={})

        # Should still work for primary embeddings
        vec = wrapper.embed_query("test")
        assert len(vec) == 384
        assert wrapper.available_models == {}

    def test_single_model_in_available_models(self, primary_embedding, secondary_embedding):
        """Test wrapper with just one model in available_models."""
        wrapper = EmbeddingsWithModels(
            embeddings=primary_embedding,
            available_models={"single-model": secondary_embedding},
        )

        assert len(wrapper.available_models) == 1
        assert "single-model" in wrapper.available_models

        # Both primary and available model should work
        primary_vec = wrapper.embed_query("test")
        single_vec = wrapper.available_models["single-model"].embed_query("test")

        assert len(primary_vec) == 384
        assert len(single_vec) == 512

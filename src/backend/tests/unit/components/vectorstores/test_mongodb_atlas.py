import os
import time
from typing import Any
from unittest.mock import MagicMock

import pytest
from langchain_community.embeddings.fake import DeterministicFakeEmbedding
from lfx.components.mongodb import MongoVectorStoreComponent
from lfx.schema.data import Data
from pymongo.collection import Collection

from tests.base import ComponentTestBaseWithoutClient, VersionComponentMapping


@pytest.mark.skipif(
    not os.environ.get("MONGODB_ATLAS_URI"), reason="Environment variable MONGODB_ATLAS_URI is not defined."
)
class TestMongoVectorStoreComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self) -> type[Any]:
        """Return the component class to test."""
        return MongoVectorStoreComponent

    @pytest.fixture
    def default_kwargs(self) -> dict[str, Any]:
        """Return the default kwargs for the component."""
        return {
            "mongodb_atlas_cluster_uri": os.getenv("MONGODB_ATLAS_URI"),
            "db_name": "test_db",
            "collection_name": "test_collection",
            "index_name": "test_index",
            "enable_mtls": False,
            "embedding": DeterministicFakeEmbedding(size=8),
            "index_field": "embedding",
            "filter_field": "text",
            "number_dimensions": 8,
            "similarity": "cosine",
            "quantization": "scalar",
            "insert_mode": "append",
            "ingest_data": [Data(data={"text": "test data 1"}), Data(data={"text": "test data 2"})],
        }

    @pytest.fixture
    def file_names_mapping(self) -> list[VersionComponentMapping]:
        """Return the file names mapping for different versions."""
        return [
            {"version": "1.0.19", "module": "vectorstores", "file_name": "MongoDBAtlasVector"},
            {"version": "1.1.0", "module": "vectorstores", "file_name": "mongodb_atlas"},
            {"version": "1.1.1", "module": "vectorstores", "file_name": "mongodb_atlas"},
        ]

    def __create_search_index(
        self, component_class: type[MongoVectorStoreComponent], collection: Collection, default_kwargs: dict[str, Any]
    ) -> None:
        """Create a vector search index if it doesn't exist."""
        component_class().set(**default_kwargs).verify_search_index(collection)

        # Verify index was created
        indexes = collection.list_search_indexes()
        index_names = {idx["name"]: idx["type"] for idx in indexes}
        index_type = index_names.get(default_kwargs["index_name"])
        assert default_kwargs["index_name"] in index_names
        assert index_type == "vectorSearch"

    def test_create_db(self, component_class: type[MongoVectorStoreComponent], default_kwargs: dict[str, Any]) -> None:
        """Test creating a MongoDB Atlas vector store."""
        component: MongoVectorStoreComponent = component_class().set(**default_kwargs)
        vector_store = component.build_vector_store()
        assert vector_store is not None
        # Access MongoDB collection through the vector store's internal client
        assert vector_store._collection.name == default_kwargs["collection_name"]
        assert vector_store._index_name == default_kwargs["index_name"]

    def test_create_collection_with_data(
        self, component_class: type[MongoVectorStoreComponent], default_kwargs: dict[str, Any]
    ) -> None:
        """Test creating a collection with data."""
        test_texts = ["test data 1", "test data 2", "something completely different"]
        default_kwargs["ingest_data"] = [Data(data={"text": text}) for text in test_texts]
        default_kwargs["insert_mode"] = "overwrite"

        component: MongoVectorStoreComponent = component_class().set(**default_kwargs)
        vector_store = component.build_vector_store()

        # Verify collection exists and has the correct data
        collection = vector_store._collection
        assert collection.name == default_kwargs["collection_name"]
        assert collection.count_documents({}) == len(test_texts)

    def test_similarity_search(
        self, component_class: type[MongoVectorStoreComponent], default_kwargs: dict[str, Any]
    ) -> None:
        """Test the similarity search functionality."""
        # Create test data with distinct topics
        test_data = [
            "The quick brown fox jumps over the lazy dog",
            "Python is a popular programming language",
            "Machine learning models process data",
            "The lazy dog sleeps all day long",
        ]
        default_kwargs["ingest_data"] = [Data(data={"text": text, "metadata": {}}) for text in test_data]
        default_kwargs["number_of_results"] = 2
        default_kwargs["insert_mode"] = "overwrite"

        # Create and initialize the component
        component: MongoVectorStoreComponent = component_class().set(**default_kwargs)

        # Build the vector store first to ensure data is ingested
        vector_store = component.build_vector_store()
        assert vector_store is not None

        # Verify documents were stored with embeddings
        documents = list(vector_store._collection.find({}))
        assert len(documents) == len(test_data)
        for doc in documents:
            assert "embedding" in doc
            assert isinstance(doc["embedding"], list)
            assert len(doc["embedding"]) == 8  # Should match our embedding size

        self.__create_search_index(component_class, vector_store._collection, default_kwargs)

        # Verify index was created
        indexes = vector_store._collection.list_search_indexes()
        index_names = [idx["name"] for idx in indexes]
        assert default_kwargs["index_name"] in index_names

        # Test similarity search through the component
        component.set(search_query="dog")
        results = component.search_documents()
        time.sleep(5)  # wait the results come from API

        assert len(results) == 2, "Expected 2 results for 'lazy dog' query"
        # The most relevant results should be about dogs
        assert any("dog" in result.data["text"].lower() for result in results)

        # Test with different number of results
        component.set(number_of_results=3)
        results = component.search_documents()
        assert len(results) == 3
        assert all("text" in result.data for result in results)

    def test_mtls_configuration(
        self, component_class: type[MongoVectorStoreComponent], default_kwargs: dict[str, Any]
    ) -> None:
        """Test mTLS configuration handling."""
        # Test with invalid mTLS configuration
        default_kwargs["enable_mtls"] = True
        default_kwargs["mongodb_atlas_client_cert"] = "invalid-cert-content"

        component: MongoVectorStoreComponent = component_class().set(**default_kwargs)
        with pytest.raises(ValueError, match="Failed to connect to MongoDB Atlas"):
            component.build_vector_store()

    def test_empty_search_query(
        self, component_class: type[MongoVectorStoreComponent], default_kwargs: dict[str, Any]
    ) -> None:
        """Test search with empty query."""
        default_kwargs["insert_mode"] = "overwrite"
        component: MongoVectorStoreComponent = component_class().set(**default_kwargs)

        # Test with empty search query
        component.set(search_query="")
        results = component.search_documents()
        assert len(results) == 0

    def test_metadata_handling(
        self, component_class: type[MongoVectorStoreComponent], default_kwargs: dict[str, Any]
    ) -> None:
        """Test handling of document metadata."""
        # Create test data with metadata
        test_data = [
            Data(data={"text": "Document 1", "metadata": {"category": "test", "priority": 1}}),
            Data(data={"text": "Document 2", "metadata": {"category": "test", "priority": 2}}),
        ]
        default_kwargs["ingest_data"] = test_data
        default_kwargs["collection_name"] = "test_collection_metadata"

        component: MongoVectorStoreComponent = component_class().set(**default_kwargs)
        vector_store = component.build_vector_store()

        self.__create_search_index(component_class, vector_store._collection, default_kwargs)

        # Test search and verify metadata is preserved
        component.set(search_query="Document", number_of_results=2)
        results = component.search_documents()

        assert len(results) == 2
        for result in results:
            assert "category" in result.data["metadata"]
            assert result.data["metadata"]["category"] == "test"
            assert "priority" in result.data["metadata"]
            assert isinstance(result.data["metadata"]["priority"], int)

    def test_error_handling(
        self, component_class: type[MongoVectorStoreComponent], default_kwargs: dict[str, Any]
    ) -> None:
        """Test error handling for invalid configurations."""
        component: MongoVectorStoreComponent = component_class().set(**default_kwargs)

        # Test with non-existent database
        default_kwargs["mongodb_atlas_cluster_uri"] = os.getenv("MONGODB_ATLAS_URI")
        default_kwargs["db_name"] = "nonexistent_db"
        component = component_class().set(**default_kwargs)

        # This should not raise an error as MongoDB creates databases and collections on demand
        vector_store = component.build_vector_store()
        assert vector_store is not None


# CI-runnable unit tests (no live MongoDB Atlas required). These cover the
# langchain-community 0.4.2 migration: MongoDBAtlasVectorSearch moved out of
# langchain_community.vectorstores into the standalone langchain_mongodb package.
# The network boundary (pymongo client + the store class) is mocked.
def _mock_component(mocker, **overrides) -> tuple[MongoVectorStoreComponent, MagicMock, MagicMock]:
    mock_client = MagicMock()
    mocker.patch("pymongo.MongoClient", return_value=mock_client)
    mock_store_cls = mocker.patch("lfx.components.mongodb.mongodb_atlas.MongoDBAtlasVectorSearch")
    kwargs = {
        "mongodb_atlas_cluster_uri": "mongodb://localhost:27017",
        "db_name": "test_db",
        "collection_name": "test_collection",
        "index_name": "test_index",
        "enable_mtls": False,
    }
    kwargs.update(overrides)
    component = MongoVectorStoreComponent(**kwargs)
    component.embedding = MagicMock()
    return component, mock_client, mock_store_cls


def test_mongodb_initialization():
    component = MongoVectorStoreComponent()
    assert component.display_name == "MongoDB Atlas"
    assert component.icon == "MongoDB"
    # The class name / identifier must remain stable: it keys saved flows.
    assert component.name == "MongoDBAtlasVector"


def test_mongodb_build_vector_store_constructs_atlas_search(mocker):
    component, mock_client, mock_store_cls = _mock_component(mocker)

    store = component.build_vector_store()

    # No ingest data -> the store is constructed directly (no from_documents).
    mock_store_cls.assert_called_once()
    mock_store_cls.from_documents.assert_not_called()
    _, kwargs = mock_store_cls.call_args
    assert kwargs["collection"] is mock_client["test_db"]["test_collection"]
    assert kwargs["index_name"] == "test_index"
    assert kwargs["embedding"] is component.embedding
    assert store is mock_store_cls.return_value


def test_mongodb_build_vector_store_with_documents_uses_from_documents(mocker):
    component, mock_client, mock_store_cls = _mock_component(mocker, insert_mode="append")
    component.ingest_data = [Data(data={"text": "hello"})]

    component.build_vector_store()

    mock_store_cls.from_documents.assert_called_once()
    _, kwargs = mock_store_cls.from_documents.call_args
    assert kwargs["collection"] is mock_client["test_db"]["test_collection"]
    assert kwargs["index_name"] == "test_index"


def test_mongodb_overwrite_insert_mode_clears_collection(mocker):
    component, mock_client, mock_store_cls = _mock_component(mocker, insert_mode="overwrite")
    component.ingest_data = [Data(data={"text": "hello"})]

    component.build_vector_store()

    collection = mock_client.__getitem__.return_value.__getitem__.return_value
    collection.delete_many.assert_called_once_with({})
    mock_store_cls.from_documents.assert_called_once()

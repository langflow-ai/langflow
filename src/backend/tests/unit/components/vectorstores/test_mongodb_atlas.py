import os
from typing import Any

import pytest
from langchain_community.embeddings.fake import DeterministicFakeEmbedding
from langchain_community.vectorstores import MongoDBAtlasVectorSearch
from langflow.components.vectorstores.mongodb_atlas import MongoVectorStoreComponent
from langflow.schema.data import Data
from pymongo.operations import SearchIndexModel

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
        }

    @pytest.fixture
    def file_names_mapping(self) -> list[VersionComponentMapping]:
        """Return the file names mapping for different versions."""
        return [
            {"version": "1.0.19", "module": "vectorstores", "file_name": "MongoDBAtlasVector"},
            {"version": "1.1.0", "module": "vectorstores", "file_name": "mongodb_atlas"},
            {"version": "1.1.1", "module": "vectorstores", "file_name": "mongodb_atlas"},
        ]

    def __create_search_index(self, vector_store: MongoDBAtlasVectorSearch, default_kwargs: dict[str, Any]) -> None:
        """Create a vector search index if it doesn't exist."""
        try:
            index_definition = SearchIndexModel(
                definition={
                    "fields": [
                        {
                            "type": "vector",
                            "path": "embedding",
                            "numDimensions": 8,
                            "similarity": "cosine",
                            "quantization": "scalar",
                        },
                        {"type": "filter", "path": "text"},
                    ]
                },
                name=default_kwargs["index_name"],
                type="vectorSearch",
            )

            vector_store._collection.create_search_index(index_definition)

            # Wait for index to be ready
            import time

            time.sleep(40)  # Give some time for index to be ready

            # Verify index was created
            indexes = vector_store._collection.list_search_indexes()
            index_names = [idx["name"] for idx in indexes]
            assert default_kwargs["index_name"] in index_names

        except Exception as e:
            # Index might already exist, which is fine
            if "AlreadyExists" not in str(e):
                raise

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

        self.__create_search_index(vector_store, default_kwargs)

        # Verify index was created
        indexes = vector_store._collection.list_search_indexes()
        index_names = [idx["name"] for idx in indexes]
        assert default_kwargs["index_name"] in index_names

        # Test similarity search through the component
        component.set(search_query="dog")
        results = component.search_documents()

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
        component: MongoVectorStoreComponent = component_class().set(**default_kwargs)
        component.build_vector_store()

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

        self.__create_search_index(vector_store, default_kwargs)

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

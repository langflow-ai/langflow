import os
from pathlib import Path
from typing import Any

import pytest
from langflow.components.vectorstores.chroma import ChromaVectorStoreComponent
from langflow.schema.data import Data

from tests.base import ComponentTestBaseWithoutClient, VersionComponentMapping


@pytest.mark.api_key_required
class TestChromaVectorStoreComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self) -> type[Any]:
        """Return the component class to test."""
        return ChromaVectorStoreComponent

    @pytest.fixture
    def default_kwargs(self, tmp_path: Path) -> dict[str, Any]:
        """Return the default kwargs for the component."""
        from langflow.components.openai.openai import OpenAIEmbeddingsComponent

        if os.getenv("OPENAI_API_KEY") is None:
            pytest.skip("OPENAI_API_KEY is not set")

        api_key = os.getenv("OPENAI_API_KEY")

        return {
            "embedding": OpenAIEmbeddingsComponent(openai_api_key=api_key).build_embeddings(),
            "collection_name": "test_collection",
            "persist_directory": tmp_path,
        }

    @pytest.fixture
    def file_names_mapping(self) -> list[VersionComponentMapping]:
        """Return the file names mapping for different versions."""
        return [
            {"version": "1.0.19", "module": "vectorstores", "file_name": "Chroma"},
            {"version": "1.1.0", "module": "vectorstores", "file_name": "chroma"},
            {"version": "1.1.1", "module": "vectorstores", "file_name": "chroma"},
        ]

    def test_create_db(self, component_class: type[ChromaVectorStoreComponent], default_kwargs: dict[str, Any]) -> None:
        """Test the create_collection method."""
        component: ChromaVectorStoreComponent = component_class().set(**default_kwargs)
        component.build_vector_store()
        persist_directory = default_kwargs["persist_directory"]
        assert persist_directory.exists()
        assert persist_directory.is_dir()
        # Assert it isn't empty
        assert len(list(persist_directory.iterdir())) > 0
        # Assert there's a chroma.sqlite3 file
        assert (persist_directory / "chroma.sqlite3").exists()
        assert (persist_directory / "chroma.sqlite3").is_file()

    def test_create_collection_with_data(
        self, component_class: type[ChromaVectorStoreComponent], default_kwargs: dict[str, Any]
    ) -> None:
        """Test the create_collection method with data."""
        # set ingest_data in default_kwargs to a list of Data objects
        test_texts = ["test data 1", "test data 2", "something completely different"]
        default_kwargs["ingest_data"] = [Data(text=text) for text in test_texts]

        component: ChromaVectorStoreComponent = component_class().set(**default_kwargs)
        vector_store = component.build_vector_store()

        # Verify collection exists and has the correct data
        collection = vector_store._collection
        assert collection.name == default_kwargs["collection_name"]
        assert collection.count() == len(test_texts)

    def test_similarity_search(
        self, component_class: type[ChromaVectorStoreComponent], default_kwargs: dict[str, Any]
    ) -> None:
        """Test the similarity search functionality through the component."""
        # Create test data with distinct topics
        test_data = [
            "The quick brown fox jumps over the lazy dog",
            "Python is a popular programming language",
            "Machine learning models process data",
            "The lazy dog sleeps all day long",
        ]
        default_kwargs["ingest_data"] = [Data(text=text) for text in test_data]
        default_kwargs["search_type"] = "Similarity"
        default_kwargs["number_of_results"] = 2

        component: ChromaVectorStoreComponent = component_class().set(**default_kwargs)
        component.build_vector_store()

        # Test similarity search through the component
        component.set(search_query="dog sleeping")
        results = component.search_documents()

        assert len(results) == 2
        # The most relevant results should be about dogs
        assert any("dog" in result.text.lower() for result in results)

        # Test with different number of results
        component.set(number_of_results=3)
        results = component.search_documents()
        assert len(results) == 3

    def test_mmr_search(
        self, component_class: type[ChromaVectorStoreComponent], default_kwargs: dict[str, Any]
    ) -> None:
        """Test the MMR search functionality through the component."""
        # Create test data with some similar documents
        test_data = [
            "The quick brown fox jumps",
            "The quick brown fox leaps",
            "The quick brown fox hops",
            "Something completely different about cats",
        ]
        default_kwargs["ingest_data"] = [Data(text=text) for text in test_data]
        default_kwargs["search_type"] = "MMR"
        default_kwargs["number_of_results"] = 3

        component: ChromaVectorStoreComponent = component_class().set(**default_kwargs)
        component.build_vector_store()

        # Test MMR search through the component
        component.set(search_query="quick fox")
        results = component.search_documents()

        assert len(results) == 3
        # Results should be diverse but relevant
        assert any("fox" in result.text.lower() for result in results)

        # Test with different settings
        component.set(number_of_results=2)
        diverse_results = component.search_documents()
        assert len(diverse_results) == 2

    def test_search_with_different_types(
        self, component_class: type[ChromaVectorStoreComponent], default_kwargs: dict[str, Any]
    ) -> None:
        """Test search with different search types."""
        test_data = [
            "The quick brown fox jumps over the lazy dog",
            "Python is a popular programming language",
            "Machine learning models process data",
        ]
        default_kwargs["ingest_data"] = [Data(text=text) for text in test_data]
        default_kwargs["number_of_results"] = 2

        component: ChromaVectorStoreComponent = component_class().set(**default_kwargs)
        component.build_vector_store()

        # Test similarity search
        component.set(search_type="Similarity", search_query="programming languages")
        similarity_results = component.search_documents()
        assert len(similarity_results) == 2
        assert any("python" in result.text.lower() for result in similarity_results)

        # Test MMR search
        component.set(search_type="MMR", search_query="programming languages")
        mmr_results = component.search_documents()
        assert len(mmr_results) == 2

        # Test with empty query
        component.set(search_query="")
        empty_results = component.search_documents()
        assert len(empty_results) == 0

    def test_search_with_score(
        self, component_class: type[ChromaVectorStoreComponent], default_kwargs: dict[str, Any]
    ) -> None:
        """Test the search with score functionality through the component."""
        test_data = [
            "The quick brown fox jumps over the lazy dog",
            "Python is a popular programming language",
            "Machine learning models process data",
        ]
        default_kwargs["ingest_data"] = [Data(text=text) for text in test_data]
        default_kwargs["number_of_results"] = 2

        component: ChromaVectorStoreComponent = component_class().set(**default_kwargs)
        component.build_vector_store()

        # Test search with score through the component
        component.set(
            search_type="similarity_score_threshold", search_query="programming languages", number_of_results=2
        )
        results = component.search_documents()

        assert len(results) == 2
        # Results should be sorted by relevance
        assert any("python" in result.text.lower() for result in results)
        assert any("programming" in result.text.lower() for result in results)

        # Test with different number of results
        component.set(number_of_results=3)
        results = component.search_documents()
        assert len(results) == 3

    def test_duplicate_handling(
        self, component_class: type[ChromaVectorStoreComponent], default_kwargs: dict[str, Any]
    ) -> None:
        """Test handling of duplicate documents."""
        # Create test data with duplicates
        test_data = [
            Data(text_key="text", data={"text": "This is a test document"}),
            Data(text_key="text", data={"text": "This is a test document"}),  # Duplicate with exact same data
            Data(text_key="text", data={"text": "This is another document"}),
        ]
        default_kwargs["ingest_data"] = test_data
        default_kwargs["allow_duplicates"] = False
        default_kwargs["limit"] = 100  # Set a high enough limit to get all documents

        component: ChromaVectorStoreComponent = component_class().set(**default_kwargs)
        vector_store = component.build_vector_store()

        # Get all documents
        results = vector_store.get(limit=100)

        documents = results["documents"]

        # The documents are returned in a list structure
        assert len(documents) == 3  # All documents are added, even duplicates

        # Count unique texts
        unique_texts = set(documents)
        assert len(unique_texts) == 2  # Should have 2 unique texts

        # Test with allow_duplicates=True
        test_data = [
            Data(text_key="text", data={"text": "This is a test document"}),
            Data(text_key="text", data={"text": "This is a test document"}),  # Duplicate
        ]
        default_kwargs["ingest_data"] = test_data
        default_kwargs["allow_duplicates"] = True
        default_kwargs["collection_name"] = "test_collection_2"  # Use a different collection name

        component = component_class().set(**default_kwargs)
        vector_store = component.build_vector_store()

        # Get all documents
        results = vector_store.get(limit=100)
        documents = results["documents"]

        # With allow_duplicates=True, we should have both documents
        assert len(documents) == 2
        assert all("test document" in doc for doc in documents)

        # Verify that we have the expected number of documents
        assert vector_store._collection.count() == 2

    def test_chroma_collection_to_data(
        self, component_class: type[ChromaVectorStoreComponent], default_kwargs: dict[str, Any]
    ) -> None:
        """Test the chroma_collection_to_data function."""
        from langflow.base.vectorstores.utils import chroma_collection_to_data

        # Create a collection with documents and metadata
        test_data = [
            Data(data={"text": "Document 1", "metadata_field": "value1"}),
            Data(data={"text": "Document 2", "metadata_field": "value2"}),
        ]
        default_kwargs["ingest_data"] = test_data
        component: ChromaVectorStoreComponent = component_class().set(**default_kwargs)
        vector_store = component.build_vector_store()

        # Get the collection data
        collection_dict = vector_store.get()
        data_objects = chroma_collection_to_data(collection_dict)

        # Verify the conversion
        assert len(data_objects) == 2
        for data_obj in data_objects:
            assert isinstance(data_obj, Data)
            assert "id" in data_obj.data
            assert "text" in data_obj.data
            assert data_obj.data["text"] in {"Document 1", "Document 2"}
            assert "metadata_field" in data_obj.data
            assert data_obj.data["metadata_field"] in {"value1", "value2"}

    def test_chroma_collection_to_data_without_metadata(
        self, component_class: type[ChromaVectorStoreComponent], default_kwargs: dict[str, Any]
    ) -> None:
        """Test the chroma_collection_to_data function with documents that have no metadata."""
        from langflow.base.vectorstores.utils import chroma_collection_to_data

        # Create a collection with documents but no metadata
        test_data = [
            Data(data={"text": "Simple document 1"}),
            Data(data={"text": "Simple document 2"}),
        ]
        default_kwargs["ingest_data"] = test_data
        component: ChromaVectorStoreComponent = component_class().set(**default_kwargs)
        vector_store = component.build_vector_store()

        # Get the collection data
        collection_dict = vector_store.get()
        data_objects = chroma_collection_to_data(collection_dict)

        # Verify the conversion
        assert len(data_objects) == 2
        for data_obj in data_objects:
            assert isinstance(data_obj, Data)
            assert "id" in data_obj.data
            assert "text" in data_obj.data
            assert data_obj.data["text"] in {"Simple document 1", "Simple document 2"}

    def test_chroma_collection_to_data_empty_collection(
        self, component_class: type[ChromaVectorStoreComponent], default_kwargs: dict[str, Any]
    ) -> None:
        """Test the chroma_collection_to_data function with an empty collection."""
        from langflow.base.vectorstores.utils import chroma_collection_to_data

        # Create an empty collection
        component: ChromaVectorStoreComponent = component_class().set(**default_kwargs)
        vector_store = component.build_vector_store()

        # Get the collection data
        collection_dict = vector_store.get()
        data_objects = chroma_collection_to_data(collection_dict)

        # Verify the conversion
        assert len(data_objects) == 0

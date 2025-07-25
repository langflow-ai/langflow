import os
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from langflow.services.cache.utils import CACHE_DIR

from lfx.components.vectorstores.local_db import LocalDBComponent
from lfx.schema.data import Data
from tests.base import ComponentTestBaseWithoutClient, VersionComponentMapping


@pytest.mark.api_key_required
class TestLocalDBComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self) -> type[Any]:
        """Return the component class to test."""
        return LocalDBComponent

    @pytest.fixture
    def default_kwargs(self, tmp_path: Path) -> dict[str, Any]:
        """Return the default kwargs for the component."""
        from lfx.components.openai.openai import OpenAIEmbeddingsComponent

        if os.getenv("OPENAI_API_KEY") is None:
            pytest.skip("OPENAI_API_KEY is not set")

        api_key = os.getenv("OPENAI_API_KEY")

        return {
            "embedding": OpenAIEmbeddingsComponent(openai_api_key=api_key).build_embeddings(),
            "collection_name": "test_collection",
            "persist": True,
            "persist_directory": str(tmp_path),  # Convert Path to string
            "mode": "Ingest",
        }

    @pytest.fixture
    def file_names_mapping(self) -> list[VersionComponentMapping]:
        """Return the file names mapping for different versions."""
        # Return an empty list since this is a new component
        return []

    def test_create_db(self, component_class: type[LocalDBComponent], default_kwargs: dict[str, Any]) -> None:
        """Test creating a vector store."""
        component: LocalDBComponent = component_class().set(**default_kwargs)
        component.build_vector_store()
        persist_directory = Path(default_kwargs["persist_directory"])
        assert persist_directory.exists()
        assert persist_directory.is_dir()
        # Assert it isn't empty
        assert len(list(persist_directory.iterdir())) > 0
        # Assert there's a chroma.sqlite3 file (since LocalDB uses Chroma underneath)
        assert (persist_directory / "chroma.sqlite3").exists()
        assert (persist_directory / "chroma.sqlite3").is_file()

    @patch("langchain_chroma.Chroma._collection")
    def test_create_db_with_data(
        self,
        mock_collection,
        component_class: type[LocalDBComponent],
        default_kwargs: dict[str, Any],
    ) -> None:
        """Test creating a vector store with data."""
        # Set ingest_data in default_kwargs to a list of Data objects
        test_texts = ["test data 1", "test data 2", "something completely different"]
        default_kwargs["ingest_data"] = [Data(text=text) for text in test_texts]

        # Mock the collection count to return the expected number
        mock_collection.count.return_value = len(test_texts)
        mock_collection.name = default_kwargs["collection_name"]

        # Mock the _add_documents_to_vector_store method to ensure add_documents is called
        with patch.object(LocalDBComponent, "_add_documents_to_vector_store") as mock_add_docs_method:
            component: LocalDBComponent = component_class().set(**default_kwargs)
            vector_store = component.build_vector_store()

            # Verify the method was called
            mock_add_docs_method.assert_called_once()

        # Verify collection exists and has the correct data
        assert vector_store._collection.name == default_kwargs["collection_name"]
        assert vector_store._collection.count() == len(test_texts)

    def test_default_persist_dir(self, component_class: type[LocalDBComponent], default_kwargs: dict[str, Any]) -> None:
        """Test the default persist directory functionality."""
        # Remove persist_directory from default_kwargs to test default directory
        default_kwargs.pop("persist_directory")

        component: LocalDBComponent = component_class().set(**default_kwargs)

        # Call get_default_persist_dir and check the result
        default_dir = component.get_default_persist_dir()
        expected_dir = Path(CACHE_DIR) / "vector_stores" / default_kwargs["collection_name"]

        assert Path(default_dir) == expected_dir
        assert Path(default_dir).exists()

    @patch("langchain_chroma.Chroma.similarity_search")
    def test_similarity_search(
        self,
        mock_similarity_search,
        component_class: type[LocalDBComponent],
        default_kwargs: dict[str, Any],
    ) -> None:
        """Test the similarity search functionality."""
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

        # Mock the similarity_search to return documents
        from langchain_core.documents import Document

        mock_docs = [
            Document(page_content="The lazy dog sleeps all day long"),
            Document(page_content="The quick brown fox jumps over the lazy dog"),
        ]
        mock_similarity_search.return_value = mock_docs

        component: LocalDBComponent = component_class().set(**default_kwargs)
        component.build_vector_store()

        # Switch to Retrieve mode
        component.set(mode="Retrieve", search_query="dog sleeping")
        results = component.search_documents()

        assert len(results) == 2
        # The most relevant results should be about dogs
        assert any("dog" in result.text.lower() for result in results)
        mock_similarity_search.assert_called_once_with(query="dog sleeping", k=2)

        # Test with different number of results
        component.set(number_of_results=3)
        another_doc = Document(page_content="Another document")
        mock_similarity_search.return_value = [*mock_docs, another_doc]  # Use unpacking instead of concatenation
        results = component.search_documents()
        assert len(results) == 3

    @patch("langchain_chroma.Chroma.max_marginal_relevance_search")
    def test_mmr_search(
        self,
        mock_mmr_search,
        component_class: type[LocalDBComponent],
        default_kwargs: dict[str, Any],
    ) -> None:
        """Test the MMR search functionality."""
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

        # Mock the MMR search to return documents
        from langchain_core.documents import Document

        mock_docs = [
            Document(page_content="The quick brown fox jumps"),
            Document(page_content="The quick brown fox leaps"),
            Document(page_content="Something completely different about cats"),
        ]
        mock_mmr_search.return_value = mock_docs

        component: LocalDBComponent = component_class().set(**default_kwargs)
        component.build_vector_store()

        # Switch to Retrieve mode
        component.set(mode="Retrieve", search_query="quick fox")
        results = component.search_documents()

        assert len(results) == 3
        # Results should be diverse but relevant
        assert any("fox" in result.text.lower() for result in results)
        mock_mmr_search.assert_called_once_with(query="quick fox", k=3)

        # Test with different settings
        component.set(number_of_results=2)
        mock_mmr_search.return_value = mock_docs[:2]
        diverse_results = component.search_documents()
        assert len(diverse_results) == 2

    @patch("langchain_chroma.Chroma.similarity_search")
    @patch("langchain_chroma.Chroma.max_marginal_relevance_search")
    def test_search_with_different_types(
        self,
        mock_mmr_search,
        mock_similarity_search,
        component_class: type[LocalDBComponent],
        default_kwargs: dict[str, Any],
    ) -> None:
        """Test search with different search types."""
        test_data = [
            "The quick brown fox jumps over the lazy dog",
            "Python is a popular programming language",
            "Machine learning models process data",
        ]
        default_kwargs["ingest_data"] = [Data(text=text) for text in test_data]
        default_kwargs["number_of_results"] = 2

        # Mock the search methods to return documents
        from langchain_core.documents import Document

        mock_similarity_docs = [
            Document(page_content="Python is a popular programming language"),
            Document(page_content="Machine learning models process data"),
        ]
        mock_similarity_search.return_value = mock_similarity_docs

        mock_mmr_docs = [
            Document(page_content="Python is a popular programming language"),
            Document(page_content="The quick brown fox jumps over the lazy dog"),
        ]
        mock_mmr_search.return_value = mock_mmr_docs

        component: LocalDBComponent = component_class().set(**default_kwargs)
        component.build_vector_store()

        # Switch to Retrieve mode and test similarity search
        component.set(mode="Retrieve", search_type="Similarity", search_query="programming languages")
        similarity_results = component.search_documents()
        assert len(similarity_results) == 2
        assert any("python" in result.text.lower() for result in similarity_results)
        mock_similarity_search.assert_called_once_with(query="programming languages", k=2)

        # Test MMR search
        component.set(search_type="MMR", search_query="programming languages")
        mmr_results = component.search_documents()
        assert len(mmr_results) == 2
        mock_mmr_search.assert_called_once_with(query="programming languages", k=2)

        # Test with empty query
        component.set(search_query="")
        empty_results = component.search_documents()
        assert len(empty_results) == 0

    @patch("langchain_chroma.Chroma.get")
    @patch("langchain_chroma.Chroma._collection")
    def test_duplicate_handling(
        self,
        mock_collection,
        mock_get,
        component_class: type[LocalDBComponent],
        default_kwargs: dict[str, Any],
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

        # Mock the get method to return documents
        mock_get.return_value = {
            "documents": ["This is a test document", "This is a test document", "This is another document"],
            "metadatas": [{}, {}, {}],
            "ids": ["1", "2", "3"],
        }

        # Mock collection count
        mock_collection.count.return_value = 3

        component: LocalDBComponent = component_class().set(**default_kwargs)
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

        # Mock for the second test
        mock_get.return_value = {
            "documents": ["This is a test document", "This is a test document"],
            "metadatas": [{}, {}],
            "ids": ["1", "2"],
        }
        mock_collection.count.return_value = 2

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

    def test_build_config_update(self, component_class: type[LocalDBComponent]) -> None:
        """Test the update_build_config method."""
        component = component_class()

        # Test mode=Ingest
        build_config = {
            "ingest_data": {"show": False},
            "collection_name": {"show": False},
            "persist": {"show": False},
            "persist_directory": {"show": False},
            "embedding": {"show": False},
            "allow_duplicates": {"show": False},
            "limit": {"show": False},
            "search_query": {"show": False},
            "search_type": {"show": False},
            "number_of_results": {"show": False},
            "existing_collections": {"show": False},
        }

        updated_config = component.update_build_config(build_config, "Ingest", "mode")

        assert updated_config["ingest_data"]["show"] is True
        assert updated_config["collection_name"]["show"] is True
        assert updated_config["persist"]["show"] is True
        assert updated_config["search_query"]["show"] is False

        # Test mode=Retrieve
        updated_config = component.update_build_config(build_config, "Retrieve", "mode")

        assert updated_config["search_query"]["show"] is True
        assert updated_config["search_type"]["show"] is True
        assert updated_config["number_of_results"]["show"] is True
        assert updated_config["existing_collections"]["show"] is True
        assert updated_config["collection_name"]["show"] is False

        # Test persist=True/False
        build_config = {"persist_directory": {"show": False}}
        # Use keyword arguments to fix FBT003
        updated_config = component.update_build_config(build_config, field_value=True, field_name="persist")
        assert updated_config["persist_directory"]["show"] is True

        updated_config = component.update_build_config(build_config, field_value=False, field_name="persist")
        assert updated_config["persist_directory"]["show"] is False

        # Test existing_collections update
        # Fix the dict entry type issue
        build_config = {"collection_name": {"value": "old_name", "show": False}}
        updated_config = component.update_build_config(build_config, "new_collection", "existing_collections")
        assert updated_config["collection_name"]["value"] == "new_collection"

    @patch("lfx.components.vectorstores.local_db.LocalDBComponent.list_existing_collections")
    def test_list_existing_collections(self, mock_list: MagicMock, component_class: type[LocalDBComponent]) -> None:
        """Test the list_existing_collections method."""
        mock_list.return_value = ["collection1", "collection2", "collection3"]

        component = component_class()
        collections = component.list_existing_collections()

        assert collections == ["collection1", "collection2", "collection3"]
        mock_list.assert_called_once()

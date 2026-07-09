from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.embeddings import Embeddings
from lfx.base.vectorstores.chroma_security import (
    chroma_client_create_collection_kwargs,
    chroma_langchain_collection_kwargs,
)
from lfx.components.chroma import ChromaVectorStoreComponent
from lfx.schema.data import Data

from tests.base import ComponentTestBaseWithoutClient, VersionComponentMapping


class _KeywordEmbeddings(Embeddings):
    _VOCAB = ("dog", "python", "programming", "machine", "learning", "fox", "cat", "quick", "test", "data")

    def _embed(self, text: str) -> list[float]:
        normalized_text = text.lower()
        return [float(normalized_text.count(term)) for term in self._VOCAB] + [float(len(normalized_text) % 17) / 17.0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


def test_remote_chroma_server_uses_http_client() -> None:
    mock_client = MagicMock()
    mock_chroma = MagicMock()
    mock_chroma.get.return_value = {"ids": [], "documents": [], "metadatas": []}

    with (
        patch("chromadb.HttpClient", return_value=mock_client) as mock_http_client,
        patch("langchain_chroma.Chroma", return_value=mock_chroma) as mock_chroma_class,
    ):
        component = ChromaVectorStoreComponent().set(
            collection_name="remote_collection",
            persist_directory=None,
            embedding=None,
            chroma_server_host="chroma.example.com",
            chroma_server_http_port=8100,
            chroma_server_ssl_enabled=True,
            ingest_data=[],
            limit=None,
        )

        assert component.build_vector_store() is mock_chroma

    mock_http_client.assert_called_once_with(host="chroma.example.com", port=8100, ssl=True)
    mock_chroma_class.assert_called_once_with(
        persist_directory=None,
        client=mock_client,
        embedding_function=None,
        collection_name="remote_collection",
        collection_configuration={"embedding_function": None},
    )


def test_chroma_collection_security_kwargs_disable_server_side_embedding_functions() -> None:
    assert chroma_langchain_collection_kwargs() == {
        "collection_configuration": {"embedding_function": None},
    }
    assert chroma_client_create_collection_kwargs() == {
        "configuration": {"embedding_function": None},
        "embedding_function": None,
    }


def test_chroma_collection_security_kwargs_are_fresh_dicts() -> None:
    first = chroma_langchain_collection_kwargs()
    first["collection_configuration"]["embedding_function"] = "unsafe"

    assert chroma_langchain_collection_kwargs() == {
        "collection_configuration": {"embedding_function": None},
    }


def test_local_chroma_collection_name_is_scoped_by_user(tmp_path: Path) -> None:
    mock_chroma = MagicMock()
    mock_chroma.get.return_value = {"ids": [], "documents": [], "metadatas": []}

    with patch("langchain_chroma.Chroma", return_value=mock_chroma) as mock_chroma_class:
        for user_id in ("owner-user", "attacker-user"):
            component = ChromaVectorStoreComponent(_user_id=user_id).set(
                collection_name="shared_collection",
                persist_directory=str(tmp_path / "shared"),
                embedding=None,
                ingest_data=[],
                limit=None,
            )
            component.build_vector_store()

    collection_names = [call.kwargs["collection_name"] for call in mock_chroma_class.call_args_list]
    assert len(collection_names) == 2
    assert collection_names[0] != "shared_collection"
    assert collection_names[1] != "shared_collection"
    assert collection_names[0] != collection_names[1]


def test_local_chroma_same_apparent_namespace_isolated_by_user(tmp_path: Path) -> None:
    shared_dir = tmp_path / "shared_chroma"
    embeddings = _KeywordEmbeddings()

    owner_component = ChromaVectorStoreComponent(_user_id="owner-user").set(
        collection_name="shared_collection",
        persist_directory=str(shared_dir),
        embedding=embeddings,
        ingest_data=[Data(text="owner-only-vector-private-content")],
        allow_duplicates=True,
        limit=100,
    )
    owner_component.build_vector_store()

    attacker_component = ChromaVectorStoreComponent(_user_id="attacker-user").set(
        collection_name="shared_collection",
        persist_directory=str(shared_dir),
        embedding=embeddings,
        ingest_data=[Data(text="attacker-vector-content")],
        allow_duplicates=True,
        limit=100,
    )
    attacker_store = attacker_component.build_vector_store()

    documents = attacker_store.get(limit=100)["documents"]
    assert "attacker-vector-content" in documents
    assert "owner-only-vector-private-content" not in documents


class TestChromaVectorStoreComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self) -> type[Any]:
        """Return the component class to test."""
        return ChromaVectorStoreComponent

    @pytest.fixture
    def default_kwargs(self, tmp_path: Path) -> dict[str, Any]:
        """Return the default kwargs for the component."""
        return {
            "embedding": _KeywordEmbeddings(),
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
        from lfx.base.vectorstores.utils import chroma_collection_to_data

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
        from lfx.base.vectorstores.utils import chroma_collection_to_data

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
        from lfx.base.vectorstores.utils import chroma_collection_to_data

        # Create an empty collection
        component: ChromaVectorStoreComponent = component_class().set(**default_kwargs)
        vector_store = component.build_vector_store()

        # Get the collection data
        collection_dict = vector_store.get()
        data_objects = chroma_collection_to_data(collection_dict)

        # Verify the conversion
        assert len(data_objects) == 0

    def test_metadata_filtering_with_complex_data(
        self, component_class: type[ChromaVectorStoreComponent], default_kwargs: dict[str, Any]
    ) -> None:
        """Test that complex metadata is properly filtered and simple types are preserved."""
        from langflow.base.vectorstores.utils import chroma_collection_to_data

        # Create test data that covers the original error scenario and validation
        test_data = [
            Data(
                data={
                    "text": "Document with mixed metadata",
                    "files": [],  # This empty list was causing the original ChromaDB error
                    "tags": ["tag1", "tag2"],  # Lists should be filtered out
                    "nested": {"key": "value"},  # Nested objects should be filtered out
                    "simple_string": "preserved",
                    "simple_int": 42,
                    "simple_bool": True,
                    "empty_string": "",  # Edge case: empty but valid
                    "zero_value": 0,  # Edge case: falsy but valid
                }
            )
        ]

        default_kwargs["ingest_data"] = test_data
        default_kwargs["collection_name"] = "test_metadata_filtering"

        # This should not raise an error despite the complex metadata
        component: ChromaVectorStoreComponent = component_class().set(**default_kwargs)
        vector_store = component.build_vector_store()

        # Verify document was added successfully
        collection_dict = vector_store.get()
        assert len(collection_dict["documents"]) == 1
        assert "Document with mixed metadata" in collection_dict["documents"][0]

        # Verify metadata filtering: simple types preserved, complex types filtered out
        data_objects = chroma_collection_to_data(collection_dict)
        data_obj = data_objects[0]

        # Simple types should be preserved
        assert data_obj.data["simple_string"] == "preserved"
        assert data_obj.data["simple_int"] == 42
        assert data_obj.data["simple_bool"] is True
        assert data_obj.data["empty_string"] == ""
        assert data_obj.data["zero_value"] == 0

        # Complex types should be filtered out
        assert "files" not in data_obj.data
        assert "tags" not in data_obj.data
        assert "nested" not in data_obj.data

    def test_metadata_filtering_fallback(
        self, component_class: type[ChromaVectorStoreComponent], default_kwargs: dict[str, Any], monkeypatch
    ) -> None:
        """Test the fallback behavior when filter_complex_metadata import fails."""
        import builtins

        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "langchain_community.vectorstores.utils":
                error_msg = "Mocked import error"
                raise ImportError(error_msg)
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)

        # Use simple test data to avoid ChromaDB errors when filtering is unavailable
        test_data = [Data(data={"text": "Simple document", "simple_field": "simple_value"})]
        default_kwargs["ingest_data"] = test_data
        default_kwargs["collection_name"] = "test_fallback"

        # Should work with fallback (no filtering)
        component: ChromaVectorStoreComponent = component_class().set(**default_kwargs)
        vector_store = component.build_vector_store()

        # Verify document was added
        collection_dict = vector_store.get()
        assert len(collection_dict["documents"]) == 1
        assert "Simple document" in collection_dict["documents"][0]

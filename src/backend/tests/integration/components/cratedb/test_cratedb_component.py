"""Invoke CrateDB using Docker.

docker run --rm -it --name=cratedb \
    --publish=4200:4200 --publish=5432:5432 \
    --env=CRATE_HEAP_SIZE=2g crate:latest \
    -Cdiscovery.type=single-node \
    -Ccluster.routing.allocation.disk.threshold_enabled=false
"""

import os
from typing import Any

import pytest
import sqlalchemy as sa
from langflow.components.vectorstores.cratedb import CrateDBVectorStoreComponent, cratedb_collection_to_data
from langflow.schema.data import Data

from tests.base import ComponentTestBaseWithoutClient, VersionComponentMapping

CRATEDB_SQLALCHEMY_URL = os.getenv("CRATEDB_SQLALCHEMY_URL", "crate://")


@pytest.fixture(autouse=True)
def cratedb_reset() -> None:
    """Cleanup: Drop all collections before tests."""
    engine = sa.create_engine(CRATEDB_SQLALCHEMY_URL)
    with engine.connect() as connection:
        connection.execute(sa.text("DROP TABLE IF EXISTS langchain_collection"))
        connection.execute(sa.text("DROP TABLE IF EXISTS langchain_embedding"))


@pytest.mark.api_key_required
class TestCrateDBVectorStoreComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self) -> type[Any]:
        """Return the component class to test."""
        return CrateDBVectorStoreComponent

    @pytest.fixture
    def default_kwargs(self) -> dict[str, Any]:
        """Return the default kwargs for the component."""
        from langflow.components.embeddings.openai import OpenAIEmbeddingsComponent

        if os.getenv("OPENAI_API_KEY") is None:
            pytest.skip("OPENAI_API_KEY is not set")

        api_key = os.getenv("OPENAI_API_KEY")

        return {
            "server_url": CRATEDB_SQLALCHEMY_URL,
            "embedding": OpenAIEmbeddingsComponent(openai_api_key=api_key).build_embeddings(),
            "collection_name": "test_collection",
        }

    @pytest.fixture
    def file_names_mapping(self) -> list[VersionComponentMapping]:
        """Return the file names mapping for different versions."""
        return []

    def test_create_db(
        self, component_class: type[CrateDBVectorStoreComponent], default_kwargs: dict[str, Any]
    ) -> None:
        """Test the create_collection method."""
        component: CrateDBVectorStoreComponent = component_class().set(**default_kwargs)
        vector_store = component.build_vector_store()
        vector_store._init_models_with_dimensionality(3)
        vector_store.create_tables_if_not_exists()
        vector_store.create_collection()

        engine = sa.create_engine(CRATEDB_SQLALCHEMY_URL)
        with engine.connect() as connection:
            connection.execute(sa.text("SELECT * FROM langchain_collection"))
            connection.execute(sa.text("SELECT * FROM langchain_embedding"))

    def test_create_collection_with_data(
        self, component_class: type[CrateDBVectorStoreComponent], default_kwargs: dict[str, Any]
    ) -> None:
        """Test the create_collection method with data."""
        # set ingest_data in default_kwargs to a list of Data objects
        test_texts = ["test data 1", "test data 2", "something completely different"]
        default_kwargs["ingest_data"] = [Data(text=text) for text in test_texts]

        component: CrateDBVectorStoreComponent = component_class().set(**default_kwargs)
        vector_store = component.build_vector_store()

        # Verify collection exists and has the correct data
        collection = vector_store.get_collection(vector_store.session_maker())
        assert collection.name == default_kwargs["collection_name"]
        assert len(collection.embeddings) == len(test_texts)

    def test_similarity_search(
        self, component_class: type[CrateDBVectorStoreComponent], default_kwargs: dict[str, Any]
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

        component: CrateDBVectorStoreComponent = component_class().set(**default_kwargs)
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
        self, component_class: type[CrateDBVectorStoreComponent], default_kwargs: dict[str, Any]
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

        component: CrateDBVectorStoreComponent = component_class().set(**default_kwargs)
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
        self, component_class: type[CrateDBVectorStoreComponent], default_kwargs: dict[str, Any]
    ) -> None:
        """Test search with different search types."""
        test_data = [
            "The quick brown fox jumps over the lazy dog",
            "Python is a popular programming language",
            "Machine learning models process data",
        ]
        default_kwargs["ingest_data"] = [Data(text=text) for text in test_data]
        default_kwargs["number_of_results"] = 2

        component: CrateDBVectorStoreComponent = component_class().set(**default_kwargs)
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
        self, component_class: type[CrateDBVectorStoreComponent], default_kwargs: dict[str, Any]
    ) -> None:
        """Test the search with score functionality through the component."""
        test_data = [
            "The quick brown fox jumps over the lazy dog",
            "Python is a popular programming language",
            "Machine learning models process data",
        ]
        default_kwargs["ingest_data"] = [Data(text=text) for text in test_data]
        default_kwargs["number_of_results"] = 2

        component: CrateDBVectorStoreComponent = component_class().set(**default_kwargs)
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

    def test_cratedb_collection_to_data(
        self, component_class: type[CrateDBVectorStoreComponent], default_kwargs: dict[str, Any]
    ) -> None:
        """Test the cratedb_collection_to_data function."""
        # Create a collection with documents and metadata
        test_data = [
            Data(data={"text": "Document 1", "metadata_field": "value1"}),
            Data(data={"text": "Document 2", "metadata_field": "value2"}),
        ]
        default_kwargs["ingest_data"] = test_data
        component: CrateDBVectorStoreComponent = component_class().set(**default_kwargs)
        vector_store = component.build_vector_store()

        # Get the collection data
        collection = vector_store.get_collection(vector_store.session_maker())
        collection_dict = collection.embeddings
        data_objects = cratedb_collection_to_data(collection_dict)

        # Verify the conversion
        assert len(data_objects) == 2
        for data_obj in data_objects:
            assert isinstance(data_obj, Data)
            assert "id" in data_obj.data
            assert "text" in data_obj.data
            assert data_obj.data["text"] in ["Document 1", "Document 2"]
            assert "metadata_field" in data_obj.data
            assert data_obj.data["metadata_field"] in ["value1", "value2"]

    def test_cratedb_collection_to_data_without_metadata(
        self, component_class: type[CrateDBVectorStoreComponent], default_kwargs: dict[str, Any]
    ) -> None:
        """Test the cratedb_collection_to_data function with documents that have no metadata."""
        # Create a collection with documents but no metadata
        test_data = [
            Data(data={"text": "Simple document 1"}),
            Data(data={"text": "Simple document 2"}),
        ]
        default_kwargs["ingest_data"] = test_data
        component: CrateDBVectorStoreComponent = component_class().set(**default_kwargs)
        vector_store = component.build_vector_store()

        # Get the collection data
        collection = vector_store.get_collection(vector_store.session_maker())
        collection_dict = collection.embeddings
        data_objects = cratedb_collection_to_data(collection_dict)

        # Verify the conversion
        assert len(data_objects) == 2
        for data_obj in data_objects:
            assert isinstance(data_obj, Data)
            assert "id" in data_obj.data
            assert "text" in data_obj.data
            assert data_obj.data["text"] in ["Simple document 1", "Simple document 2"]

    def test_cratedb_collection_to_data_empty_collection(
        self, component_class: type[CrateDBVectorStoreComponent], default_kwargs: dict[str, Any]
    ) -> None:
        """Test the cratedb_collection_to_data function with an empty collection."""
        # Create an empty collection
        component: CrateDBVectorStoreComponent = component_class().set(**default_kwargs)
        vector_store = component.build_vector_store()

        # Get the collection data
        with pytest.raises(RuntimeError) as ex:
            vector_store.get_collection(vector_store.session_maker())
        assert ex.match("Collection can't be accessed without specifying dimension size of embedding vectors")

    def test_component_versions(self, *args, **kwargs) -> None:  # noqa: ARG002
        pytest.skip("Component versions can't be tested for new components")

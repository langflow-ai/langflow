import os
import time
from typing import Any

import pytest
from lfx.components.vectorstores.db2 import DB2VectorStoreComponent
from lfx.schema.data import Data

from tests.base import ComponentTestBaseWithoutClient


@pytest.mark.skipif(not os.environ.get("DB2_CONN_STR"), reason="Environment variable DB2_CONN_STR is not defined.")
class TestDB2VectorStoreComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self) -> type[Any]:
        """Return the component class to test."""
        return DB2VectorStoreComponent

    @pytest.fixture
    def default_kwargs(self) -> dict[str, Any]:
        """Return the default kwargs for the component."""
        from lfx.components.openai.openai import OpenAIEmbeddingsComponent

        from tests.api_keys import get_openai_api_key

        try:
            api_key = get_openai_api_key()
        except ValueError:
            pytest.skip("OPENAI_API_KEY is not set")

        return {
            "conn_str": os.getenv("DB2_CONN_STR"),
            "table_name": "t1",
            "embedding": OpenAIEmbeddingsComponent(openai_api_key=api_key).build_embeddings(),
            "distance_strategy": "DOT_PRODUCT",
            "ingest_data": [Data(data={"text": "test data 1"}), Data(data={"text": "test data 2"})],
        }

    def test_create_db(self, component_class: type[DB2VectorStoreComponent], default_kwargs: dict[str, Any]) -> None:
        """Test creating a IBM Db2 vector store."""
        component: DB2VectorStoreComponent = component_class().set(**default_kwargs)
        vector_store = component.build_vector_store()
        assert vector_store is not None

    def test_similarity_search(
        self, component_class: type[DB2VectorStoreComponent], default_kwargs: dict[str, Any]
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
        default_kwargs["search_type"] = "Similarity"
        default_kwargs["number_of_results"] = 2

        # Create and initialize the component
        component: DB2VectorStoreComponent = component_class().set(**default_kwargs)

        # Build the vector store first to ensure data is ingested
        vector_store = component.build_vector_store()
        assert vector_store is not None

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

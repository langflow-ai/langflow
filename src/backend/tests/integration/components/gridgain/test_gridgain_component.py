import os
import unittest

from base.langflow.components.vectorstores.gridgain import GridGainVectorStoreComponent
from langchain.embeddings import OpenAIEmbeddings
from langchain.schema import Document
from langflow.schema import Data
from pygridgain import Client


class TestGridGainVectorStore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up test environment once before all tests."""
        cls.api_key = os.getenv("OPENAI_API_KEY")
        if not cls.api_key:
            msg = "OPENAI_API_KEY environment variable is required"
            raise OSError(msg)

    def setUp(self):
        """Set up test environment before each test."""
        self.host = "localhost"
        self.port = 10800
        self.cache_name = "test_vector_store"

        # Initialize component
        self.component = GridGainVectorStoreComponent()
        self.component.host = self.host
        self.component.port = self.port
        self.component.cache_name = self.cache_name
        self.component.score_threshold = 0.6
        self.component.number_of_results = 4

        # Use real OpenAI embeddings
        self.embeddings = OpenAIEmbeddings()
        self.component.embedding = self.embeddings

        # Connect to GridGain and clear test cache

        self.client = Client()
        self.client.connect(self.host, self.port)
        test_cache = self.client.get_or_create_cache(self.cache_name)
        test_cache.clear()

    def count_cache_entries(self, cache):
        """Helper function to count entries in the GridGain cache."""
        return sum(1 for _ in cache.scan())

    def create_test_data(self):
        """Create test Data objects for ingest_data testing."""
        test_data = []
        for i in range(1, 4):
            data = Data(
                content=f"This is content for integration test {i}",
                metadata={
                    "id": i,
                    "title": f"Integration Test {i}",
                    "url": f"http://test{i}.com",
                    "vector_id": f"v{i}",
                },
            )
            test_data.append(data)
        return test_data

    def test_1_connection(self):
        """Test real GridGain connection."""
        from pygridgain import Client

        client = Client()
        client.connect(self.host, self.port)
        assert client.connect()

        # Verify we can interact with the cache
        cache = client.get_or_create_cache(self.cache_name)
        assert cache

    def test_2_build_vector_store(self):
        """Test actual vector store creation and initialization."""
        vector_store = self.component.build_vector_store()
        assert vector_store is not None
        assert vector_store.cache_name == self.cache_name, (
            f"Expected cache name {self.cache_name}, \
            but got {vector_store.cache_name}"
        )

        # Verify the cache exists in GridGain
        cache_names = self.client.get_cache_names()
        assert self.cache_name in cache_names, f"Cache name {self.cache_name} not found in GridGain"

    def test_3_process_and_store_data(self):
        """Test data processing and storage using ingest_data."""
        # Create test data
        test_data = self.create_test_data()

        # Set ingest_data on the component
        self.component.ingest_data = test_data

        # Build vector store which should process and store the data
        self.component.build_vector_store()

        # Use correct cache entry counting
        cache = self.client.get_cache(self.cache_name)
        cache_size = self.count_cache_entries(cache)
        assert cache_size == 3, f"Expected 3 entries, found {cache_size}"

    def test4_search_documents(self):
        """Test searching documents within the vector store."""
        # Ingest test data first
        test_data = self.create_test_data()
        self.component.ingest_data = test_data

        # Perform a search with an explicit query
        query = "Integration Test"
        results = self.component.search_documents(query)

        # Validate results
        assert isinstance(results, list), "Search results should be a list."

    def test_5_search_with_threshold(self):
        """Test search with different score thresholds."""
        # Ingest test data before searching
        test_data = [
            Document(page_content="Specific technical content about GridGain caches", metadata={"id": "1"}),
            Document(page_content="Completely unrelated content about Gridgain", metadata={"id": "2"}),
        ]

        vector_store = self.component.build_vector_store()
        vector_store.add_documents(test_data)

        # Perform searches with different thresholds
        query = "GridGain caches"

        self.component.score_threshold = 0.9
        high_threshold_results = self.component.search_documents(query)

        self.component.score_threshold = 0.1
        low_threshold_results = self.component.search_documents(query)

        # Lower threshold should return more results
        assert len(low_threshold_results) >= len(high_threshold_results), "Lower threshold should return more results."

    def tearDown(self):
        """Clean up after each test."""
        if hasattr(self, "client") and self.client.connect():
            cache = self.client.get_cache(self.cache_name)
            if cache:
                cache.clear()
            self.client.close()


if __name__ == "__main__":
    unittest.main()

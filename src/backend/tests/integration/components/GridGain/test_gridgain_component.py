import unittest
import pandas as pd
import tempfile
import os
from langchain.schema import Document
from langchain.embeddings import OpenAIEmbeddings
from base.langflow.components.vectorstores.gridgain import GridGainVectorStoreComponent

class TestGridGainVectorStore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up test environment once before all tests."""
        cls.api_key = os.getenv("OPENAI_API_KEY")
        if not cls.api_key:
            raise EnvironmentError("OPENAI_API_KEY environment variable is required")

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
        self.client = self.component.connect_to_gridgain(self.host, self.port)
        test_cache = self.client.get_or_create_cache(self.cache_name)
        test_cache.clear()

    def count_cache_entries(self, cache):
        """Helper function to count entries in the GridGain cache."""
        return sum(1 for _ in cache.scan())


    def create_test_csv(self):
        """Create a temporary CSV file for testing."""
        data = {
            'id': [1, 2, 3],
            'title': ['Integration Test 1', 'Integration Test 2', 'Integration Test 3'],
            'text': ['This is content for integration test 1', 
                    'This is content for integration test 2', 
                    'This is content for integration test 3'],
            'url': ['http://test1.com', 'http://test2.com', 'http://test3.com'],
            'vector_id': ['v1', 'v2', 'v3']
        }
        df = pd.DataFrame(data)
        
        temp_dir = tempfile.mkdtemp()
        csv_path = os.path.join(temp_dir, 'test.csv')
        df.to_csv(csv_path, index=False)
        return csv_path

    def test_1_connection(self):
        """Test real GridGain connection."""
        client = self.component.connect_to_gridgain(self.host, self.port)
        self.assertTrue(client.connect())
        
        # Verify we can interact with the cache
        cache = client.get_or_create_cache(self.cache_name)
        self.assertIsNotNone(cache)

    def test_2_build_vector_store(self):
        """Test actual vector store creation and initialization."""
        vector_store = self.component.build_vector_store()
        self.assertIsNotNone(vector_store)
        self.assertEqual(vector_store.cache_name, self.cache_name)
        
        # Verify the cache exists in GridGain
        cache_names = self.client.get_cache_names()
        self.assertIn(self.cache_name, cache_names)

    def test_3_process_and_store_csv(self):
        """Test CSV processing and storage."""
        csv_path = self.create_test_csv()
        try:
            self.component.csv_file = csv_path
            vector_store = self.component.build_vector_store()
            
            # Use correct cache entry counting
            cache = self.client.get_cache(self.cache_name)
            cache_size = self.count_cache_entries(cache)
            self.assertEqual(cache_size, 3, f"Expected 3 entries, found {cache_size}")
            
        finally:
            os.remove(csv_path)

    def test_search_documents(self):
        """Test searching documents within the vector store."""
        # Set search query and number of results
        self.component.search_query = "test search"
        self.component.number_of_results = 2

        try:
            results = self.component.search_documents()
            self.assertIsInstance(results, list, "Search results should be a list.")
            print(f"Found {len(results)} documents matching query.")
        except Exception as e:
            self.fail(f"Search failed with exception: {e}")

    def test_5_search_with_threshold(self):
        """Test search with different score thresholds."""
        test_docs = [
            Document(
                page_content="Specific technical content about GridGain caches",
                metadata={"id": "1"}
            ),
            Document(
                page_content="Completely unrelated content about gardening",
                metadata={"id": "2"}
            )
        ]
        
        vector_store = self.component.build_vector_store()
        vector_store.add_documents(test_docs)
        
        # Test with high threshold
        self.component.score_threshold = 0.9
        self.component.search_query = "GridGain cache configuration"
        high_threshold_results = self.component.search_documents()
        
        # Test with lower threshold
        self.component.score_threshold = 0.1
        low_threshold_results = self.component.search_documents()
        
        # Lower threshold should return more results
        self.assertTrue(len(low_threshold_results) >= len(high_threshold_results))

    def tearDown(self):
        """Clean up after each test."""
        if hasattr(self, 'client') and self.client.connect():
            cache = self.client.get_cache(self.cache_name)
            if cache:
                cache.clear()
            self.client.close()

if __name__ == '__main__':
    unittest.main()

import pytest
import pandas as pd
from unittest.mock import Mock, patch, MagicMock
from langchain.schema import Document
from langchain_community.vectorstores.ignite import GridGainVectorStore
from pygridgain import Client
from typing import List
import tempfile
import os

# Import the class to test
from base.langflow.components.vectorstores.gridgain import GridGainVectorStoreComponent

@pytest.fixture
def component():
    """Create a basic component instance for testing."""
    component = GridGainVectorStoreComponent()
    component.cache_name = "test_cache"
    component.host = "localhost"
    component.port = 10800
    component.embedding = Mock()
    return component

@pytest.fixture
def sample_csv_content():
    """Create sample CSV content for testing."""
    return """id,title,text,url,vector_id
1,Test Title 1,Test Content 1,http://test1.com,vec1
2,Test Title 2,Test Content 2,http://test2.com,vec2
3,,Just Content 3,http://test3.com,vec3"""

@pytest.fixture
def sample_csv_file(sample_csv_content):
    """Create a temporary CSV file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
        f.write(sample_csv_content)
        return f.name

class TestGridGainVectorStoreComponent:
    def test_initialization(self, component):
        """Test basic component initialization."""
        assert component.cache_name == "test_cache"
        assert component.host == "localhost"
        assert component.port == 10800
        assert component.embedding is not None

    def test_process_csv_valid_file(self, component: GridGainVectorStoreComponent, sample_csv_file):
        """Test processing a valid CSV file."""
        documents = component.process_csv(sample_csv_file)
        
        assert isinstance(documents, list)
        assert len(documents) == 3
        assert all(isinstance(doc, Document) for doc in documents)
        
        # Check first document content and metadata
        assert "Test Title 1\nTest Content 1" in documents[0].page_content
        assert documents[0].metadata == {
            "id": "1",
            "url": "http://test1.com",
            "vector_id": "vec1"
        }

    def test_process_csv_missing_columns(self, component):
        """Test processing CSV with missing columns."""
        minimal_csv = """text
Some content
Another content"""
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
            f.write(minimal_csv)
            csv_path = f.name

        documents = component.process_csv(csv_path)
        assert len(documents) == 2
        assert documents[0].metadata == {"id": "", "url": "", "vector_id": ""}
        
        os.unlink(csv_path)

    def test_process_csv_invalid_file(self, component: GridGainVectorStoreComponent):
        """Test processing an invalid CSV file."""
        with pytest.raises(Exception):
            component.process_csv("nonexistent_file.csv")

    @patch('base.langflow.components.vectorstores.gridGain.Client')
    def test_connect_to_ignite(self, mock_client, component):
        """Test connection to GridGain server."""
        mock_client_instance = MagicMock()
        mock_client.return_value = mock_client_instance
        
        result = component.connect_to_gridgain(component.host, component.port)
        
        mock_client.assert_called_once()
        mock_client_instance.connect.assert_called_once_with(component.host, component.port)
        assert result == mock_client_instance

    @patch('base.langflow.components.vectorstores.gridGain.Client')
    def test_build_vector_store_without_csv(self, mock_client, component):
        """Test building vector store without CSV input."""
        # Setup mock client
        mock_client_instance = MagicMock()
        mock_client.return_value = mock_client_instance
        
        # Setup mock GridGainVectorStore
        with patch('base.langflow.components.vectorstores.gridGain.GridGainVectorStore') as mock_gridgain:
            mock_gridgain_instance = MagicMock()
            mock_gridgain.return_value = mock_gridgain_instance
            
            vector_store = component.build_vector_store()
            
            mock_client.assert_called_once()
            mock_gridgain.assert_called_once_with(
                cache_name="test_cache",
                embedding=component.embedding,
                client=mock_client_instance
            )
            assert vector_store == mock_gridgain_instance

    @patch('base.langflow.components.vectorstores.gridGain.Client')
    def test_build_vector_store_with_csv(self, mock_client, component, sample_csv_file):
        """Test building vector store with CSV input."""
        # Setup mock client
        mock_client_instance = MagicMock()
        mock_client.return_value = mock_client_instance
        
        # Setup mock GridGainVectorStore
        with patch('base.langflow.components.vectorstores.gridGain.GridGainVectorStore') as mock_gridgain:
            mock_gridgain_instance = MagicMock()
            mock_gridgain.return_value = mock_gridgain_instance
            
            component.csv_file = sample_csv_file
            vector_store = component.build_vector_store()
            
            mock_client.assert_called_once()
            mock_gridgain.assert_called_once()
            mock_gridgain_instance.add_documents.assert_called_once()
            assert component.status.startswith("Added")

    def test_search_documents_empty_query(self, component):
        """Test search with empty query."""
        component.search_query = ""
        results = component.search_documents()
        
        assert results == []
        assert "No search query provided" in component.status

    @patch('base.langflow.components.vectorstores.gridGain.Client')
    def test_search_documents_error_handling(self, mock_client, component):
        """Test search error handling."""
        # Setup mock client to raise an exception
        mock_client.side_effect = Exception("Test error")
        
        component.search_query = "test query"
        results = component.search_documents()
        
        assert results == []
        assert "Search error: Test error" in component.status

    def test_connection_error_handling(self, component):
        """Test handling of connection errors."""
        with pytest.raises(Exception):
            component.connect_to_ignite("invalid_host", -1)

    def teardown_method(self, method):
        """Cleanup after tests."""
        if hasattr(self, 'temp_csv_path'):
            try:
                os.unlink(self.temp_csv_path)
            except:
                pass
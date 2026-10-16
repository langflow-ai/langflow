from unittest.mock import MagicMock, patch

import httpx
import pytest
from langflow.components.mem0.search_memories import SearchMemoriesComponent
from langflow.schema import DataFrame

from tests.base import ComponentTestBaseWithoutClient


class TestSearchMemoriesComponent(ComponentTestBaseWithoutClient):
    """Test class for SearchMemoriesComponent."""

    @pytest.fixture
    def component_class(self):
        """Return the component class to be tested."""
        return SearchMemoriesComponent

    @pytest.fixture
    def default_kwargs(self):
        """Return default arguments for initializing the component."""
        return {
            "api_key": "test_api_key",
            "query": "test search query",
            "mem0_user_id": "test_user_id",
            "agent_ids": "agent1,agent2",
            "app_id": "test_app_id",
            "run_id": "test_run_id",
            "created_at_gte": "2025-01-01",
            "created_at_lte": "2025-03-01",
            "logic_operator": "AND",
            "top_k": 5,
            "rerank": True,
        }

    @pytest.fixture
    def file_names_mapping(self):
        """Return file names mapping for the component."""
        # This is a new component, so no previous versions exist
        return []

    def test_validate_inputs_success(self, component_class, default_kwargs):
        """Test validate_inputs method with valid inputs."""
        component = component_class(**default_kwargs)
        # Should not raise any exceptions
        component.validate_inputs()

    def test_validate_inputs_missing_query(self, component_class, default_kwargs):
        """Test validate_inputs method with missing query."""
        default_kwargs["query"] = ""
        component = component_class(**default_kwargs)
        with pytest.raises(ValueError, match="Search query is required"):
            component.validate_inputs()

    def test_validate_inputs_missing_api_key(self, component_class, default_kwargs):
        """Test validate_inputs method with missing API key."""
        default_kwargs["api_key"] = ""
        component = component_class(**default_kwargs)
        with pytest.raises(ValueError, match="API Key is required"):
            component.validate_inputs()

    def test_validate_inputs_invalid_date_format_gte(self, component_class, default_kwargs):
        """Test validate_inputs method with invalid date format for created_at_gte."""
        default_kwargs["created_at_gte"] = "01-01-2025"  # Wrong format
        component = component_class(**default_kwargs)
        with pytest.raises(ValueError, match="Invalid date format for 'Created After' field"):
            component.validate_inputs()

    def test_validate_inputs_invalid_date_format_lte(self, component_class, default_kwargs):
        """Test validate_inputs method with invalid date format for created_at_lte."""
        default_kwargs["created_at_lte"] = "01/01/2025"  # Wrong format
        component = component_class(**default_kwargs)
        with pytest.raises(ValueError, match="Invalid date format for 'Created Before' field"):
            component.validate_inputs()

    def test_build_filters(self, component_class, default_kwargs):
        """Test build_filters method."""
        component = component_class(**default_kwargs)
        filters = component.build_filters()

        # Check that all filters are correctly built
        assert filters["user_id"] == "test_user_id"
        assert filters["app_id"] == "test_app_id"
        assert filters["run_id"] == "test_run_id"
        assert filters["agent_id"] == {"in": ["agent1", "agent2"]}
        assert filters["created_at"] == {"gte": "2025-01-01", "lte": "2025-03-01"}

    def test_build_filters_empty(self, component_class):
        """Test build_filters method with empty inputs."""
        component = component_class(api_key="test_api_key", query="test query")
        filters = component.build_filters()

        # Should return an empty dict
        assert filters == {}

    @patch("langflow.components.mem0.search_memories.httpx.Client")
    def test_search_memories_response_success(self, mock_client, component_class, default_kwargs):
        """Test search_memories_response method with successful API response."""
        # Mock the httpx.Client and its post method
        mock_client_instance = MagicMock()
        mock_client.return_value.__enter__.return_value = mock_client_instance

        # Sample memory data that would be returned by the API
        sample_memories = [
            {
                "id": "mem_123",
                "user_id": "test_user_id",
                "agent_id": "agent1",
                "app_id": "test_app_id",
                "memory": "Test memory content",
                "created_at": "2025-01-15",
                "updated_at": "2025-01-15",
                "metadata": {"source": "test"},
                "categories": ["category1"],
                "hash": "abc123",
                "score": 0.95,
            }
        ]

        # Mock the response object
        mock_response = MagicMock()
        mock_response.status_code = 200  # HTTP_STATUS_OK
        mock_response.json.return_value = sample_memories
        mock_client_instance.post.return_value = mock_response

        component = component_class(**default_kwargs)
        result = component.search_memories_response()

        # Verify the result is a DataFrame
        assert isinstance(result, DataFrame)

        # Verify the client was called with the correct parameters
        mock_client_instance.post.assert_called_once()
        call_args, call_kwargs = mock_client_instance.post.call_args
        assert call_args[0] == "https://api.mem0.ai/v2/memories/search/"
        assert "json" in call_kwargs
        assert call_kwargs["json"]["query"] == "test search query"
        assert "filters" in call_kwargs["json"]
        assert call_kwargs["json"]["top_k"] == 5
        assert call_kwargs["json"]["rerank"] is True

    @patch("langflow.components.mem0.search_memories.httpx.Client")
    def test_search_memories_response_api_error(self, mock_client, component_class, default_kwargs):
        """Test search_memories_response method with API error."""
        # Mock the httpx.Client and its post method
        mock_client_instance = MagicMock()
        mock_client.return_value.__enter__.return_value = mock_client_instance

        # Mock the response object with an error
        mock_response = MagicMock()
        mock_response.status_code = 400  # Bad Request
        mock_response.text = "Invalid query format"
        mock_client_instance.post.return_value = mock_response

        component = component_class(**default_kwargs)
        result = component.search_memories_response()

        # Verify the result is a DataFrame
        assert isinstance(result, DataFrame)
        # We don't need to check the internal structure, just that it's a DataFrame

    @patch("langflow.components.mem0.search_memories.httpx.Client")
    def test_search_memories_response_exception(self, mock_client, component_class, default_kwargs):
        """Test search_memories_response method with exception."""
        # Mock the httpx.Client and its post method to raise an exception
        mock_client_instance = MagicMock()
        mock_client.return_value.__enter__.return_value = mock_client_instance
        mock_client_instance.post.side_effect = httpx.HTTPStatusError(
            "Connection error", request=MagicMock(), response=MagicMock()
        )

        component = component_class(**default_kwargs)
        result = component.search_memories_response()

        # Verify the result is a DataFrame
        assert isinstance(result, DataFrame)
        # We don't need to check the internal structure, just that it's a DataFrame

    def test_to_frontend_node(self, component_class, default_kwargs):
        """Test to_frontend_node method."""
        component = component_class(**default_kwargs)
        frontend_node = component.to_frontend_node()

        # Check that the frontend node has the expected structure
        assert "data" in frontend_node
        assert "node" in frontend_node["data"]

        node_data = frontend_node["data"]["node"]

        # Check that API key is in the template
        assert "api_key" in node_data["template"]
        # Check that the API key field is marked as password/secret
        assert node_data["template"]["api_key"]["password"]

        # Check that query field is required
        assert "query" in node_data["template"]
        assert node_data["template"]["query"]["required"]

        # Check that other fields are in the template
        assert "mem0_user_id" in node_data["template"]
        assert "agent_ids" in node_data["template"]
        assert "app_id" in node_data["template"]
        assert "run_id" in node_data["template"]
        assert "created_at_gte" in node_data["template"]
        assert "created_at_lte" in node_data["template"]
        assert "logic_operator" in node_data["template"]
        assert "top_k" in node_data["template"]
        assert "rerank" in node_data["template"]

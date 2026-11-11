import asyncio
from unittest.mock import MagicMock, patch

import pytest
from langflow.components.mem0.manage_memories import ManageMemoriesComponent
from langflow.schema import Data

from tests.base import ComponentTestBaseWithoutClient


class TestManageMemoriesComponent(ComponentTestBaseWithoutClient):
    """Test class for ManageMemoriesComponent."""

    @pytest.fixture
    def component_class(self):
        """Return the component class to be tested."""
        return ManageMemoriesComponent

    @pytest.fixture
    def default_kwargs(self):
        """Return default arguments for initializing the component."""
        return {
            "api_key": "test_api_key",
            "operation": "Add",
            "memory_id": "test_memory_id",
            "messages": ["Test message content"],
            "mem0_user_id": "test_user_id",
            "agent_id": "test_agent_id",
            "app_id": "test_app_id",
            "session_id": "test_session_id",
            "async_mode": False,
            "infer": False,
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

    def test_validate_inputs_missing_api_key(self, component_class, default_kwargs):
        """Test validate_inputs method with missing API key."""
        default_kwargs["api_key"] = ""
        component = component_class(**default_kwargs)
        with pytest.raises(ValueError, match="API Key is required"):
            component.validate_inputs()

    def test_validate_inputs_missing_messages_for_add(self, component_class, default_kwargs):
        """Test validate_inputs method with missing messages for Add operation."""
        default_kwargs["messages"] = []
        component = component_class(**default_kwargs)
        with pytest.raises(ValueError, match="Messages are required for Add and Update operations"):
            component.validate_inputs()

    def test_validate_inputs_missing_memory_id_for_get(self, component_class, default_kwargs):
        """Test validate_inputs method with missing memory_id for Get operation."""
        default_kwargs["operation"] = "Get"
        default_kwargs["memory_id"] = ""
        component = component_class(**default_kwargs)
        with pytest.raises(ValueError, match="Memory ID is required for Get, Update, and Delete operations"):
            component.validate_inputs()

    def test_parse_messages_string(self, component_class, default_kwargs):
        """Test parse_messages method with string messages."""
        component = component_class(**default_kwargs)
        parsed = component.parse_messages()

        # Check that the string message was correctly parsed into a dict
        assert len(parsed) == 1
        assert parsed[0]["role"] == "user"
        assert parsed[0]["content"] == "Test message content"

    def test_parse_messages_dict(self, component_class, default_kwargs):
        """Test parse_messages method with dict messages."""
        default_kwargs["messages"] = [{"role": "assistant", "content": "Test response"}]
        component = component_class(**default_kwargs)
        parsed = component.parse_messages()

        # Check that the dict message was correctly passed through
        assert len(parsed) == 1
        assert parsed[0]["role"] == "assistant"
        assert parsed[0]["content"] == "Test response"

    def test_parse_messages_invalid_dict(self, component_class, default_kwargs):
        """Test parse_messages method with invalid dict messages."""
        default_kwargs["messages"] = [{"invalid_key": "missing role and content"}]
        component = component_class(**default_kwargs)
        with pytest.raises(ValueError, match="Message 1 missing required fields"):
            component.parse_messages()

    def test_parse_messages_invalid_type(self, component_class, default_kwargs):
        """Test parse_messages method with invalid message type."""
        default_kwargs["messages"] = [123]  # Not a string or dict
        component = component_class(**default_kwargs)
        with pytest.raises(ValueError, match="Error parsing message 1"):
            component.parse_messages()

    @patch("langflow.components.mem0.manage_memories.MemoryClient")
    def test_manage_memory_response_add(self, mock_client, component_class, default_kwargs):
        """Test manage_memory_response method for Add operation."""
        # Mock the MemoryClient and its add method
        mock_client_instance = MagicMock()
        mock_client.return_value = mock_client_instance

        # Sample response that would be returned by the API
        sample_response = {
            "id": "mem_123",
            "user_id": "test_user_id",
            "agent_id": "test_agent_id",
            "app_id": "test_app_id",
            "messages": [{"role": "user", "content": "Test message content"}],
        }
        mock_client_instance.add.return_value = sample_response

        component = component_class(**default_kwargs)
        component.session_id = "test_session_id"

        if asyncio.iscoroutinefunction(component.manage_memory_response):
            result = asyncio.run(component.manage_memory_response())
        else:
            result = component.manage_memory_response()

        # Verify the result is a Data object
        assert isinstance(result, Data)

        # Verify the client was called with the correct parameters
        mock_client_instance.add.assert_called_once()

    @patch("langflow.components.mem0.manage_memories.MemoryClient")
    def test_manage_memory_response_update(self, mock_client, component_class, default_kwargs):
        """Test manage_memory_response method for Update operation."""
        default_kwargs["operation"] = "Update"
        default_kwargs["memory_id"] = "mem_123"

        # Mock the MemoryClient and its update method
        mock_client_instance = MagicMock()
        mock_client.return_value = mock_client_instance

        # Sample response that would be returned by the API
        sample_response = {
            "id": "mem_123",
            "user_id": "test_user_id",
            "agent_id": "test_agent_id",
            "app_id": "test_app_id",
            "messages": [{"role": "user", "content": "Updated message content"}],
        }
        mock_client_instance.update.return_value = sample_response

        component = component_class(**default_kwargs)
        component.session_id = "test_session_id"

        if asyncio.iscoroutinefunction(component.manage_memory_response):
            result = asyncio.run(component.manage_memory_response())
        else:
            result = component.manage_memory_response()

        # Verify the result is a Data object
        assert isinstance(result, Data)

    @patch("langflow.components.mem0.manage_memories.MemoryClient")
    def test_manage_memory_response_get(self, mock_client, component_class, default_kwargs):
        """Test manage_memory_response method for Get operation."""
        default_kwargs["operation"] = "Get"
        default_kwargs["memory_id"] = "mem_123"

        # Mock the MemoryClient and its get method
        mock_client_instance = MagicMock()
        mock_client.return_value = mock_client_instance

        # Sample response that would be returned by the API
        sample_response = {
            "id": "mem_123",
            "user_id": "test_user_id",
            "agent_id": "test_agent_id",
            "app_id": "test_app_id",
            "messages": [{"role": "user", "content": "Test message content"}],
        }
        mock_client_instance.get.return_value = sample_response

        component = component_class(**default_kwargs)
        component.session_id = "test_session_id"

        if asyncio.iscoroutinefunction(component.manage_memory_response):
            result = asyncio.run(component.manage_memory_response())
        else:
            result = component.manage_memory_response()

        # Verify the result is a Data object
        assert isinstance(result, Data)

    @patch("langflow.components.mem0.manage_memories.MemoryClient")
    def test_manage_memory_response_delete(self, mock_client, component_class, default_kwargs):
        """Test manage_memory_response method for Delete operation."""
        default_kwargs["operation"] = "Delete"
        default_kwargs["memory_id"] = "mem_123"

        # Mock the MemoryClient and its delete method
        mock_client_instance = MagicMock()
        mock_client.return_value = mock_client_instance

        # Sample response that would be returned by the API
        sample_response = {"success": True}
        mock_client_instance.delete.return_value = sample_response

        component = component_class(**default_kwargs)
        component.session_id = "test_session_id"

        if asyncio.iscoroutinefunction(component.manage_memory_response):
            result = asyncio.run(component.manage_memory_response())
        else:
            result = component.manage_memory_response()

        # Verify the result is a Data object
        assert isinstance(result, Data)

    @patch("langflow.components.mem0.manage_memories.MemoryClient")
    def test_manage_memory_response_error(self, mock_client, component_class, default_kwargs):
        """Test manage_memory_response method with API error."""
        # Mock the MemoryClient and its add method to raise an exception
        mock_client_instance = MagicMock()
        mock_client.return_value = mock_client_instance
        mock_client_instance.add.side_effect = ValueError("API validation error")

        component = component_class(**default_kwargs)
        component.session_id = "test_session_id"

        if asyncio.iscoroutinefunction(component.manage_memory_response):
            result = asyncio.run(component.manage_memory_response())
        else:
            result = component.manage_memory_response()

        # Verify the result is a Data object with error information
        assert isinstance(result, Data)

    @patch("langflow.components.mem0.manage_memories.AsyncMemoryClient")
    def test_manage_memory_response_async(self, mock_async_client, component_class, default_kwargs):
        """Test manage_memory_response method with async mode."""
        default_kwargs["async_mode"] = True

        # Mock the AsyncMemoryClient and its add method
        mock_client_instance = MagicMock()
        mock_async_client.return_value = mock_client_instance

        # Sample response that would be returned by the API
        sample_response = {
            "id": "mem_123",
            "user_id": "test_user_id",
            "agent_id": "test_agent_id",
            "app_id": "test_app_id",
            "messages": [{"role": "user", "content": "Test message content"}],
        }

        # Create a coroutine function that returns the sample response
        async def mock_add_async(**_kwargs):
            return sample_response

        # Assign the mock coroutine to the add method
        mock_client_instance.add = mock_add_async

        component = component_class(**default_kwargs)
        component.session_id = "test_session_id"

        if asyncio.iscoroutinefunction(component.manage_memory_response):
            result = asyncio.run(component.manage_memory_response())
        else:
            result = component.manage_memory_response()

        # Verify the result is a Data object
        assert isinstance(result, Data)

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

        # Check that operation field is a dropdown with the correct options
        assert "operation" in node_data["template"]
        assert node_data["template"]["operation"]["options"] == ["Add", "Update", "Get", "Delete"]

        # Check that other fields are in the template
        assert "memory_id" in node_data["template"]
        assert "messages" in node_data["template"]
        assert "mem0_user_id" in node_data["template"]
        assert "agent_id" in node_data["template"]
        assert "app_id" in node_data["template"]
        assert "session_id" in node_data["template"]
        assert "async_mode" in node_data["template"]
        assert "infer" in node_data["template"]

"""Tests for SpecAPIClient."""

import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import httpx
from langflow.components.helpers.studio_builder.api_client import SpecAPIClient


class TestSpecAPIClient:
    """Test SpecAPIClient class."""

    @pytest.fixture
    async def client(self):
        """Create SpecAPIClient instance."""
        client = SpecAPIClient()
        await client.__aenter__()
        yield client
        await client.__aexit__(None, None, None)

    @pytest.mark.asyncio
    async def test_get_knowledge_success(self):
        """Test successful knowledge retrieval."""
        async with SpecAPIClient() as api_client:
            with patch.object(api_client, '_get_client') as mock_get_client:
                # Mock the HTTP client
                mock_http_client = AsyncMock()
                mock_response = MagicMock()
                mock_response.json.return_value = {
                    "success": True,
                    "knowledge": {
                        "components": {
                            "genesis:agent": {"component": "Agent", "config": {}},
                            "genesis:chat_input": {"component": "ChatInput", "config": {}}
                        }
                    },
                    "message": "Success"
                }
                mock_response.status_code = 200
                mock_http_client.post.return_value = mock_response
                mock_get_client.return_value = mock_http_client

                # Test the method
                result = await api_client.get_knowledge(query_type="components")

                assert result is not None
                assert "components" in result
                assert "genesis:agent" in result["components"]
                assert result["components"]["genesis:agent"]["component"] == "Agent"

                # Verify the API was called correctly
                mock_http_client.post.assert_called_once_with(
                    "/api/v1/spec/knowledge",
                    json={"query_type": "components", "reload_cache": False}
                )

    @pytest.mark.asyncio
    async def test_get_knowledge_http_error(self):
        """Test knowledge retrieval with HTTP error."""
        async with SpecAPIClient() as api_client:
            with patch.object(api_client, '_get_client') as mock_get_client:
                # Mock HTTP error
                mock_http_client = AsyncMock()
                mock_http_client.post.side_effect = httpx.HTTPStatusError(
                    "Server error",
                    request=Mock(),
                    response=Mock(status_code=500)
                )
                mock_get_client.return_value = mock_http_client

                # Should raise an exception
                with pytest.raises(Exception) as exc_info:
                    await api_client.get_knowledge(query_type="components")

                assert "Failed to get knowledge from API: 500" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_knowledge_api_failure(self):
        """Test knowledge retrieval when API returns failure."""
        async with SpecAPIClient() as api_client:
            with patch.object(api_client, '_get_client') as mock_get_client:
                # Mock API failure response
                mock_http_client = AsyncMock()
                mock_response = MagicMock()
                mock_response.json.return_value = {
                    "success": False,
                    "knowledge": {},
                    "message": "Failed to load components"
                }
                mock_response.status_code = 200
                mock_http_client.post.return_value = mock_response
                mock_get_client.return_value = mock_http_client

                # Should raise an exception
                with pytest.raises(Exception) as exc_info:
                    await api_client.get_knowledge(query_type="components")

                assert "Knowledge API failed" in str(exc_info.value)
                assert "Failed to load components" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_validate_spec_success(self):
        """Test successful spec validation."""
        async with SpecAPIClient() as api_client:
            with patch.object(api_client, '_get_client') as mock_get_client:
                # Mock successful validation
                mock_http_client = AsyncMock()
                mock_response = MagicMock()
                mock_response.json.return_value = {
                    "valid": True,
                    "errors": [],
                    "warnings": ["Minor warning"]
                }
                mock_response.status_code = 200
                mock_http_client.post.return_value = mock_response
                mock_get_client.return_value = mock_http_client

                # Test the method
                result = await api_client.validate_spec("test: yaml")

                assert result["valid"] is True
                assert len(result["errors"]) == 0
                assert len(result["warnings"]) == 1
                assert result["warnings"][0] == "Minor warning"

                # Verify API call
                mock_http_client.post.assert_called_once_with(
                    "/api/v1/spec/validate",
                    json={"spec_yaml": "test: yaml"}
                )

    @pytest.mark.asyncio
    async def test_get_available_components_success(self):
        """Test successful component retrieval."""
        async with SpecAPIClient() as api_client:
            with patch.object(api_client, '_get_client') as mock_get_client:
                # Mock successful response
                mock_http_client = AsyncMock()
                mock_response = MagicMock()
                mock_response.json.return_value = {
                    "components": {
                        "genesis:agent": {"name": "Agent", "description": "Agent component"},
                        "genesis:mcp_tool": {"name": "MCP Tool", "description": "MCP tool component"}
                    }
                }
                mock_response.status_code = 200
                mock_http_client.get.return_value = mock_response
                mock_get_client.return_value = mock_http_client

                # Test the method
                result = await api_client.get_available_components()

                assert "genesis:agent" in result
                assert result["genesis:agent"]["name"] == "Agent"
                assert "genesis:mcp_tool" in result

                # Verify API call
                mock_http_client.get.assert_called_once_with("/api/v1/spec/components")

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test SpecAPIClient as context manager."""
        client = SpecAPIClient()

        # Test entering context
        await client.__aenter__()
        assert client.session is not None

        # Test exiting context
        await client.__aexit__(None, None, None)
        # Session should be closed after exit

    @pytest.mark.asyncio
    async def test_get_client(self):
        """Test _get_client method."""
        async with SpecAPIClient() as api_client:
            # Mock the session
            api_client.session = AsyncMock()

            # Create a mock client
            mock_client = Mock()
            api_client.session.client.return_value = mock_client

            # Test _get_client
            client = await api_client._get_client()

            assert client == mock_client
            api_client.session.client.assert_called_once_with(
                base_url="http://localhost:7860",
                headers={"Content-Type": "application/json"},
                timeout=30.0
            )

    @pytest.mark.asyncio
    async def test_reload_cache_parameter(self):
        """Test reload_cache parameter is passed correctly."""
        async with SpecAPIClient() as api_client:
            with patch.object(api_client, '_get_client') as mock_get_client:
                mock_http_client = AsyncMock()
                mock_response = MagicMock()
                mock_response.json.return_value = {
                    "success": True,
                    "knowledge": {},
                    "message": "Success"
                }
                mock_response.status_code = 200
                mock_http_client.post.return_value = mock_response
                mock_get_client.return_value = mock_http_client

                # Test with reload_cache=True
                await api_client.get_knowledge(query_type="all", reload_cache=True)

                # Verify reload_cache was passed
                mock_http_client.post.assert_called_with(
                    "/api/v1/spec/knowledge",
                    json={"query_type": "all", "reload_cache": True}
                )
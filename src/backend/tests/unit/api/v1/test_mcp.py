from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import status
from httpx import AsyncClient
from langflow.services.auth.utils import get_password_hash
from langflow.services.database.models.user import User

# Mark all tests in this module as asyncio
pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_user():
    return User(
        id=uuid4(), username="testuser", password=get_password_hash("testpassword"), is_active=True, is_superuser=False
    )


@pytest.fixture
def mock_mcp_server():
    with patch("langflow.api.v1.mcp.server") as mock:
        # Basic mocking for server attributes potentially accessed during endpoint calls
        mock.request_context = MagicMock()
        mock.request_context.meta = MagicMock()
        mock.request_context.meta.progressToken = "test_token"
        mock.request_context.session = AsyncMock()
        mock.create_initialization_options = MagicMock()
        mock.run = AsyncMock()
        yield mock


@pytest.fixture
def mock_sse_transport():
    with patch("langflow.api.v1.mcp.sse") as mock:
        mock.connect_sse = AsyncMock()
        mock.handle_post_message = AsyncMock()
        yield mock


# Fixture to mock the current user context variable needed for auth in /sse GET
@pytest.fixture(autouse=True)
def mock_current_user_ctx(mock_user):
    with patch("langflow.api.v1.mcp.current_user_ctx") as mock:
        mock.get.return_value = mock_user
        mock.set = MagicMock(return_value="dummy_token")  # Return a dummy token for reset
        mock.reset = MagicMock()
        yield mock


# Test the HEAD /sse endpoint (checks server availability)
async def test_mcp_sse_head_endpoint(client: AsyncClient):
    """Test HEAD /sse endpoint returns 200 OK."""
    response = await client.head("api/v1/mcp/sse")
    assert response.status_code == status.HTTP_200_OK


# Test the HEAD /sse endpoint without authentication
async def test_mcp_sse_head_endpoint_no_auth(client: AsyncClient):
    """Test HEAD /sse endpoint without authentication returns 200 OK (HEAD requests don't require auth)."""
    response = await client.head("api/v1/mcp/sse")
    assert response.status_code == status.HTTP_200_OK


async def test_mcp_sse_get_endpoint_invalid_auth(client: AsyncClient):
    """Test GET /sse endpoint with invalid authentication returns 401."""
    headers = {"Authorization": "Bearer invalid_token"}
    response = await client.get("api/v1/mcp/sse", headers=headers)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


# Test the POST / endpoint (handles incoming MCP messages)
async def test_mcp_post_endpoint_success(client: AsyncClient, logged_in_headers, mock_sse_transport):
    """Test POST / endpoint successfully handles MCP messages."""
    test_message = {"type": "test", "content": "message"}
    response = await client.post("api/v1/mcp/", headers=logged_in_headers, json=test_message)

    assert response.status_code == status.HTTP_200_OK
    mock_sse_transport.handle_post_message.assert_called_once()


async def test_mcp_post_endpoint_no_auth(client: AsyncClient):
    """Test POST / endpoint without authentication returns 400 (current behavior)."""
    response = await client.post("api/v1/mcp/", json={})
    assert response.status_code == status.HTTP_400_BAD_REQUEST


async def test_mcp_post_endpoint_invalid_json(client: AsyncClient, logged_in_headers):
    """Test POST / endpoint with invalid JSON returns 400."""
    response = await client.post("api/v1/mcp/", headers=logged_in_headers, content="invalid json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST


async def test_mcp_post_endpoint_disconnect_error(client: AsyncClient, logged_in_headers, mock_sse_transport):
    """Test POST / endpoint handles disconnection errors correctly."""
    mock_sse_transport.handle_post_message.side_effect = BrokenPipeError("Simulated disconnect")

    response = await client.post("api/v1/mcp/", headers=logged_in_headers, json={"type": "test"})

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "MCP Server disconnected" in response.json()["detail"]
    mock_sse_transport.handle_post_message.assert_called_once()


async def test_mcp_post_endpoint_server_error(client: AsyncClient, logged_in_headers, mock_sse_transport):
    """Test POST / endpoint handles server errors correctly."""
    mock_sse_transport.handle_post_message.side_effect = Exception("Internal server error")

    response = await client.post("api/v1/mcp/", headers=logged_in_headers, json={"type": "test"})

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert "Internal server error" in response.json()["detail"]

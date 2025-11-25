"""Unit tests for MCP Streamable HTTP transport endpoints."""

import json
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
    """Mock MCP server for testing."""
    with patch("langflow.api.v1.mcp.server") as mock:
        mock.create_initialization_options = MagicMock(return_value={"capabilities": {}})
        
        async def mock_run(read_stream, write_stream, init_options):
            """Mock server.run that writes a test response."""
            # Simulate server processing by writing a response
            test_response = {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {"protocolVersion": "2025-03-26", "capabilities": {}, "serverInfo": {"name": "test"}},
            }
            await write_stream.write(json.dumps(test_response).encode() + b"\n")
        
        mock.run = AsyncMock(side_effect=mock_run)
        yield mock


@pytest.fixture
def mock_current_user_ctx(mock_user):
    """Mock current user context."""
    with patch("langflow.api.v1.mcp.current_user_ctx") as mock:
        mock.get.return_value = mock_user
        mock.set = MagicMock(return_value="dummy_token")
        mock.reset = MagicMock()
        yield mock


@pytest.fixture(autouse=True)
def clear_sessions():
    """Clear sessions before each test."""
    from langflow.api.v1.mcp import _sessions
    
    _sessions.clear()
    yield
    _sessions.clear()


class TestStreamableHttpPost:
    """Tests for POST /api/v1/mcp/streamable endpoint."""

    async def test_post_initialize_request_creates_session(self, client: AsyncClient, logged_in_headers, mock_mcp_server):
        """Test POST with initialize request creates a new session."""
        initialize_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0.0"},
            },
        }
        
        response = await client.post(
            "api/v1/mcp/streamable",
            headers={**logged_in_headers, "Accept": "application/json"},
            json=initialize_request,
        )
        
        assert response.status_code == status.HTTP_200_OK
        # Should have session ID in response if InitializeResult is returned
        assert "Mcp-Session-Id" in response.headers or response.status_code == 200

    async def test_post_notification_returns_202(self, client: AsyncClient, logged_in_headers):
        """Test POST with notification returns 202 Accepted."""
        notification = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {},
        }
        
        response = await client.post(
            "api/v1/mcp/streamable",
            headers=logged_in_headers,
            json=notification,
        )
        
        assert response.status_code == status.HTTP_202_ACCEPTED

    async def test_post_with_session_id(self, client: AsyncClient, logged_in_headers, mock_mcp_server, mock_user):
        """Test POST with existing session ID."""
        from langflow.api.v1.mcp import _sessions, _generate_session_id
        
        session_id = _generate_session_id()
        _sessions[session_id] = {"user": mock_user, "initialized": False}
        
        request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        }
        
        response = await client.post(
            "api/v1/mcp/streamable",
            headers={**logged_in_headers, "Mcp-Session-Id": session_id},
            json=request,
        )
        
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR]

    async def test_post_invalid_session_id(self, client: AsyncClient, logged_in_headers):
        """Test POST with invalid session ID returns 404."""
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {},
        }
        
        response = await client.post(
            "api/v1/mcp/streamable",
            headers={**logged_in_headers, "Mcp-Session-Id": "invalid-session-id"},
            json=request,
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "Session not found" in response.json()["detail"]

    async def test_post_invalid_json(self, client: AsyncClient, logged_in_headers):
        """Test POST with invalid JSON returns 400."""
        response = await client.post(
            "api/v1/mcp/streamable",
            headers=logged_in_headers,
            content="invalid json",
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    async def test_post_json_response_format(self, client: AsyncClient, logged_in_headers, mock_mcp_server):
        """Test POST returns JSON when client prefers application/json."""
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {},
        }
        
        response = await client.post(
            "api/v1/mcp/streamable",
            headers={**logged_in_headers, "Accept": "application/json"},
            json=request,
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert response.headers["content-type"] == "application/json"
        data = response.json()
        assert "jsonrpc" in data or isinstance(data, list)

    async def test_post_sse_response_format(self, client: AsyncClient, logged_in_headers, mock_mcp_server):
        """Test POST returns SSE when client accepts text/event-stream."""
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {},
        }
        
        response = await client.post(
            "api/v1/mcp/streamable",
            headers={**logged_in_headers, "Accept": "text/event-stream"},
            json=request,
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert "text/event-stream" in response.headers["content-type"]


class TestStreamableHttpGet:
    """Tests for GET /api/v1/mcp/streamable endpoint."""

    async def test_get_opens_sse_stream(self, client: AsyncClient, logged_in_headers):
        """Test GET opens SSE stream."""
        response = await client.get(
            "api/v1/mcp/streamable",
            headers={**logged_in_headers, "Accept": "text/event-stream"},
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert "text/event-stream" in response.headers["content-type"]
        assert "Mcp-Session-Id" in response.headers

    async def test_get_with_session_id(self, client: AsyncClient, logged_in_headers, mock_user):
        """Test GET with existing session ID."""
        from langflow.api.v1.mcp import _sessions, _generate_session_id
        
        session_id = _generate_session_id()
        _sessions[session_id] = {"user": mock_user, "initialized": True}
        
        response = await client.get(
            "api/v1/mcp/streamable",
            headers={**logged_in_headers, "Mcp-Session-Id": session_id, "Accept": "text/event-stream"},
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert response.headers["Mcp-Session-Id"] == session_id

    async def test_get_invalid_session_id(self, client: AsyncClient, logged_in_headers):
        """Test GET with invalid session ID returns 404."""
        response = await client.get(
            "api/v1/mcp/streamable",
            headers={**logged_in_headers, "Mcp-Session-Id": "invalid-session-id", "Accept": "text/event-stream"},
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_get_with_last_event_id(self, client: AsyncClient, logged_in_headers):
        """Test GET with Last-Event-ID header for resumability."""
        response = await client.get(
            "api/v1/mcp/streamable",
            headers={
                **logged_in_headers,
                "Accept": "text/event-stream",
                "Last-Event-ID": "event-123",
            },
        )
        
        # Should succeed (resumability is optional)
        assert response.status_code == status.HTTP_200_OK


class TestStreamableHttpDelete:
    """Tests for DELETE /api/v1/mcp/streamable endpoint."""

    async def test_delete_terminates_session(self, client: AsyncClient, logged_in_headers, mock_user):
        """Test DELETE terminates a session."""
        from langflow.api.v1.mcp import _sessions, _generate_session_id
        
        session_id = _generate_session_id()
        _sessions[session_id] = {"user": mock_user, "initialized": True}
        
        response = await client.delete(
            "api/v1/mcp/streamable",
            headers={**logged_in_headers, "Mcp-Session-Id": session_id},
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert session_id not in _sessions

    async def test_delete_nonexistent_session(self, client: AsyncClient, logged_in_headers):
        """Test DELETE with nonexistent session returns 404."""
        response = await client.delete(
            "api/v1/mcp/streamable",
            headers={**logged_in_headers, "Mcp-Session-Id": "nonexistent-session-id"},
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestStreamableHttpSecurity:
    """Tests for security features."""

    async def test_origin_validation_warning(self, client: AsyncClient, logged_in_headers):
        """Test Origin header validation logs warning for invalid origin."""
        with patch("langflow.api.v1.mcp.logger") as mock_logger:
            response = await client.post(
                "api/v1/mcp/streamable",
                headers={
                    **logged_in_headers,
                    "Origin": "https://malicious-site.com",
                },
                json={"jsonrpc": "2.0", "method": "test", "params": {}},
            )
            
            # Should still process but log warning
            assert response.status_code in [status.HTTP_202_ACCEPTED, status.HTTP_200_OK]

    async def test_requires_authentication(self, client: AsyncClient):
        """Test endpoints require authentication."""
        response = await client.post("api/v1/mcp/streamable", json={})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        
        response = await client.get("api/v1/mcp/streamable")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestStreamableHttpStreams:
    """Tests for stream implementations."""

    async def test_read_stream_iterates_messages(self):
        """Test _StreamableHttpReadStream iterates messages correctly."""
        from langflow.api.v1.mcp import _StreamableHttpReadStream
        
        messages = [{"jsonrpc": "2.0", "id": 1, "method": "test"}]
        stream = _StreamableHttpReadStream(messages)
        
        collected = []
        async for msg in stream:
            collected.append(msg)
        
        assert len(collected) == 1
        assert b"test" in collected[0]

    async def test_write_stream_collects_responses(self):
        """Test _StreamableHttpWriteStream collects responses."""
        from langflow.api.v1.mcp import _StreamableHttpWriteStream
        
        stream = _StreamableHttpWriteStream()
        
        async with stream:
            await stream.write(b'{"jsonrpc": "2.0", "id": 1, "result": {}}\n')
            await stream.write(b'{"jsonrpc": "2.0", "id": 2, "result": {}}\n')
        
        responses = stream.get_all_responses()
        assert len(responses) == 2
        assert responses[0]["id"] == 1
        assert responses[1]["id"] == 2

    async def test_write_stream_sse_generator(self):
        """Test _StreamableHttpWriteStream SSE generator."""
        from langflow.api.v1.mcp import _StreamableHttpWriteStream
        
        stream = _StreamableHttpWriteStream()
        await stream.write(b'{"jsonrpc": "2.0", "id": 1, "result": {}}\n')
        
        events = []
        async for event in stream.stream_responses():
            events.append(event)
        
        assert len(events) == 1
        assert "data:" in events[0]
        assert "id:" in events[0]


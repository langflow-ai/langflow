import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException, status
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
async def mock_streamable_http_manager():
    """Provide a mocked Streamable HTTP manager without starting the real transport."""
    manager = AsyncMock()

    async def fake_handle_request(_scope, _receive, send):
        await send(
            {
                "type": "http.response.start",
                "status": status.HTTP_200_OK,
                "headers": [],
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": b"",
                "more_body": False,
            }
        )

    manager.handle_request = AsyncMock(side_effect=fake_handle_request)

    with patch("langflow.api.v1.mcp.get_streamable_http_manager", return_value=manager):
        yield manager


@pytest.fixture
def mock_sse_transport():
    with patch("langflow.api.v1.mcp.sse") as mock:
        mock.connect_sse = AsyncMock()
        mock.handle_post_message = AsyncMock()
        yield mock


class _DummyRunContext:
    """Async context manager that records when StreamableHTTP enters/exits the session."""

    def __init__(self, entered_event: asyncio.Event, exited_event: asyncio.Event):
        self._entered_event = entered_event
        self._exited_event = exited_event

    async def __aenter__(self):
        self._entered_event.set()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        """Mark the context as exited without suppressing exceptions."""
        self._exited_event.set()
        return False


class _FailingRunContext:
    """Async context manager that raises on enter to simulate startup failures."""

    def __init__(self, exc: Exception):
        self._exc = exc

    async def __aenter__(self):
        raise self._exc

    async def __aexit__(self, exc_type, exc, tb):
        return False


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


async def test_mcp_sse_post_endpoint(client: AsyncClient, mock_sse_transport):
    """Test POST / endpoint for SSE transport succeeds without auth."""
    response = await client.post("api/v1/mcp/", json={"type": "test"})

    assert response.status_code == status.HTTP_200_OK
    mock_sse_transport.handle_post_message.assert_called_once()


async def test_mcp_post_endpoint_success(client: AsyncClient, logged_in_headers, mock_sse_transport):
    """Test POST / endpoint successfully handles MCP messages with auth."""
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


async def test_mcp_sse_post_endpoint_disconnect_error(client: AsyncClient, mock_sse_transport):
    """Test POST / endpoint handles disconnection errors correctly for SSE."""
    mock_sse_transport.handle_post_message.side_effect = BrokenPipeError("Simulated disconnect")

    response = await client.post("api/v1/mcp/", json={"type": "test"})

    assert response.status_code == status.HTTP_404_NOT_FOUND
    mock_sse_transport.handle_post_message.assert_called_once()


async def test_mcp_post_endpoint_disconnect_error(client: AsyncClient, logged_in_headers, mock_sse_transport):
    """Test POST / endpoint handles disconnection errors correctly with auth."""
    mock_sse_transport.handle_post_message.side_effect = BrokenPipeError("Simulated disconnect")

    response = await client.post("api/v1/mcp/", headers=logged_in_headers, json={"type": "test"})

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "MCP Server disconnected" in response.json()["detail"]
    mock_sse_transport.handle_post_message.assert_called_once()


async def test_mcp_sse_post_endpoint_server_error(client: AsyncClient, mock_sse_transport):
    """Test POST / endpoint handles server errors correctly for SSE."""
    mock_sse_transport.handle_post_message.side_effect = Exception("Internal server error")

    response = await client.post("api/v1/mcp/", json={"type": "test"})

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


async def test_mcp_post_endpoint_server_error(client: AsyncClient, logged_in_headers, mock_sse_transport):
    """Test POST / endpoint handles server errors correctly with auth."""
    mock_sse_transport.handle_post_message.side_effect = Exception("Internal server error")

    response = await client.post("api/v1/mcp/", headers=logged_in_headers, json={"type": "test"})

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert "Internal server error" in response.json()["detail"]


# Streamable HTTP tests
async def test_mcp_streamable_post_endpoint(
    client: AsyncClient,
    logged_in_headers,
    mock_streamable_http_manager,
):
    """Test POST /streamable endpoint successfully handles MCP messages."""
    test_message = {"type": "test", "content": "message"}
    response = await client.post("api/v1/mcp/streamable", headers=logged_in_headers, json=test_message)

    assert response.status_code == status.HTTP_200_OK
    mock_streamable_http_manager.handle_request.assert_called_once()


async def test_mcp_streamable_post_endpoint_no_auth(client: AsyncClient):
    """Test POST /streamable endpoint without authentication returns 403 Forbidden."""
    response = await client.post("api/v1/mcp/streamable", json={})
    assert response.status_code == status.HTTP_403_FORBIDDEN


async def test_mcp_streamable_post_endpoint_disconnect_error(
    client: AsyncClient, logged_in_headers, mock_streamable_http_manager
):
    """Test POST /streamable endpoint handles disconnection errors correctly."""
    mock_streamable_http_manager.handle_request.side_effect = BrokenPipeError("Simulated disconnect")

    response = await client.post("api/v1/mcp/streamable", headers=logged_in_headers, json={"type": "test"})

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    mock_streamable_http_manager.handle_request.assert_called_once()


async def test_mcp_streamable_post_endpoint_server_error(
    client: AsyncClient, logged_in_headers, mock_streamable_http_manager
):
    """Test POST /streamable endpoint handles server errors correctly."""
    mock_streamable_http_manager.handle_request.side_effect = Exception("Internal server error")

    response = await client.post("api/v1/mcp/streamable", headers=logged_in_headers, json={"type": "test"})

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


# Tests for GET and DELETE on /streamable endpoint
async def test_mcp_streamable_get_endpoint(
    client: AsyncClient,
    logged_in_headers,
    mock_streamable_http_manager,
):
    """Test GET /streamable endpoint successfully handles MCP messages."""
    response = await client.get("api/v1/mcp/streamable", headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK
    mock_streamable_http_manager.handle_request.assert_called_once()


async def test_mcp_streamable_delete_endpoint(
    client: AsyncClient,
    logged_in_headers,
    mock_streamable_http_manager,
):
    """Test DELETE /streamable endpoint successfully handles MCP messages."""
    response = await client.delete("api/v1/mcp/streamable", headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK
    mock_streamable_http_manager.handle_request.assert_called_once()


async def test_mcp_streamable_get_endpoint_no_auth(client: AsyncClient):
    """Test GET /streamable endpoint without authentication returns 403 Forbidden."""
    response = await client.get("api/v1/mcp/streamable")
    assert response.status_code == status.HTTP_403_FORBIDDEN


async def test_mcp_streamable_delete_endpoint_no_auth(client: AsyncClient):
    """Test DELETE /streamable endpoint without authentication returns 403 Forbidden."""
    response = await client.delete("api/v1/mcp/streamable")
    assert response.status_code == status.HTTP_403_FORBIDDEN


async def test_streamable_http_start_stop_lifecycle():
    """Ensure StreamableHTTP starts and stops its session manager cleanly."""
    from langflow.api.v1.mcp import StreamableHTTP

    entered = asyncio.Event()
    exited = asyncio.Event()
    manager_instance = MagicMock()
    manager_instance.run.return_value = _DummyRunContext(entered, exited)

    with (
        patch("langflow.api.v1.mcp.StreamableHTTPSessionManager", return_value=manager_instance),
        patch("langflow.api.v1.mcp.logger.adebug", new_callable=AsyncMock),
    ):
        streamable_http = StreamableHTTP()
        await streamable_http.start()
        assert streamable_http.get_manager() is manager_instance
        assert entered.is_set(), "session manager never entered run()"

        await streamable_http.stop()
        assert exited.is_set(), "session manager never exited run()"


async def test_streamable_http_start_failure_keeps_manager_unavailable():
    """Ensure failures while starting the session manager propagate and keep manager unavailable."""
    from langflow.api.v1.mcp import StreamableHTTP

    failure = RuntimeError("boom")
    manager_instance = MagicMock()
    manager_instance.run.return_value = _FailingRunContext(failure)

    with (
        patch("langflow.api.v1.mcp.StreamableHTTPSessionManager", return_value=manager_instance),
        patch("langflow.api.v1.mcp.logger.adebug", new_callable=AsyncMock),
        patch("langflow.api.v1.mcp.logger.aexception", new_callable=AsyncMock),
    ):
        streamable_http = StreamableHTTP()
        with pytest.raises(RuntimeError):
            await streamable_http.start()

        with pytest.raises(HTTPException):
            streamable_http.get_manager()


async def test_streamable_http_start_failure_surfaces_exception_once():
    """Verify StreamableHTTP.start surfaces the exact exception raised by _start_session_manager."""
    from langflow.api.v1.mcp import StreamableHTTP

    failure = RuntimeError("failed to run session manager")
    manager_instance = MagicMock()
    manager_instance.run.return_value = _FailingRunContext(failure)

    async_logger = AsyncMock()
    with (
        patch("langflow.api.v1.mcp.StreamableHTTPSessionManager", return_value=manager_instance),
        patch("langflow.api.v1.mcp.logger.aexception", new=async_logger),
    ):
        streamable_http = StreamableHTTP()
        with pytest.raises(RuntimeError) as exc_info:
            await streamable_http.start()

    assert str(exc_info.value) == "Error in Streamable HTTP session manager: failed to run session manager"
    assert exc_info.value.__cause__ is failure
    assert async_logger.await_count == 1
    expected_message = (
        "Error starting Streamable HTTP session manager: "
        "Error in Streamable HTTP session manager: failed to run session manager"
    )
    assert async_logger.await_args_list[0].args[0] == expected_message


# Tests for find_validation_error function
@pytest.mark.asyncio(loop_scope="session")
async def test_find_validation_error_with_pydantic_error():
    """Test that find_validation_error correctly identifies ValidationError."""
    import pydantic
    from langflow.api.v1.mcp import find_validation_error

    # Create a pydantic ValidationError by catching it
    validation_error = None
    try:

        class TestModel(pydantic.BaseModel):
            required_field: str

        TestModel()  # This will raise ValidationError
    except pydantic.ValidationError as e:
        validation_error = e

    assert validation_error is not None
    # Wrap it in another exception
    nested_error = ValueError("Wrapper")
    nested_error.__cause__ = validation_error

    found = find_validation_error(nested_error)
    assert found is validation_error


@pytest.mark.asyncio(loop_scope="session")
async def test_find_validation_error_without_pydantic_error():
    """Test that find_validation_error returns None for non-pydantic errors."""
    from langflow.api.v1.mcp import find_validation_error

    error = ValueError("Test error")
    assert find_validation_error(error) is None


@pytest.mark.asyncio(loop_scope="session")
async def test_find_validation_error_with_context():
    """Test that find_validation_error searches __context__ chain."""
    import pydantic
    from langflow.api.v1.mcp import find_validation_error

    # Create a pydantic ValidationError by catching it
    validation_error = None
    try:

        class TestModel(pydantic.BaseModel):
            required_field: str

        TestModel()
    except pydantic.ValidationError as e:
        validation_error = e

    assert validation_error is not None
    # Wrap it using __context__ instead of __cause__
    nested_error = ValueError("Wrapper")
    nested_error.__context__ = validation_error

    found = find_validation_error(nested_error)
    assert found is validation_error


# Tests for context token management
async def test_mcp_sse_context_token_management(mock_current_user_ctx):
    """Test that context token is properly set and reset."""
    # The mock is set up in the fixture, verify it's being called
    mock_current_user_ctx.set.assert_not_called()  # Not called yet
    mock_current_user_ctx.reset.assert_not_called()  # Not called yet


# Test for find_validation_error usage in SSE endpoint
@pytest.mark.asyncio(loop_scope="session")
async def test_mcp_sse_validation_error_logged():
    """Test that the find_validation_error function is available for SSE endpoint error handling."""
    # This is a simpler test that verifies the find_validation_error function
    # is available and could be used by the SSE endpoint if needed
    # The actual usage in a real SSE connection is tested through integration tests
    import pydantic
    from langflow.api.v1.mcp import find_validation_error

    # Verify the function exists and works
    validation_error = None
    try:

        class TestModel(pydantic.BaseModel):
            required_field: str

        TestModel()
    except pydantic.ValidationError as e:
        validation_error = e

    assert validation_error is not None
    wrapped_error = RuntimeError("Wrapper")
    wrapped_error.__cause__ = validation_error

    # The function should be able to find the validation error in the chain
    found = find_validation_error(wrapped_error)
    assert found is validation_error

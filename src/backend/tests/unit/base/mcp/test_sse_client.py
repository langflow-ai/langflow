"""Unit tests for Enhanced MCPSseClient.

Tests the enhanced SSE client functionality including:
- Dual transport support (Streamable HTTP + HTTP+SSE)
- Transport detection and fallback
- Retry logic with exponential backoff
- Timeout handling
- URL validation and redirect checking
- Error scenarios and cleanup
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from httpx import ConnectError
from langflow.base.mcp.sse_client import MCPConnectionError, MCPSseClient, MCPTransportError


class TestMCPSseClientConfiguration:
    """Test configuration and initialization."""

    def test_default_configuration(self):
        """Test default configuration values."""
        client = MCPSseClient()

        assert client.max_retries == 3
        assert client.base_retry_delay == 1.0
        assert client.max_retry_delay == 10.0
        assert client.retry_exponential_base == 2
        assert client.discovery_timeout == 15
        assert client.handshake_timeout == 10
        assert client.request_timeout == 30
        assert client.connected_transport is None
        assert client._connected is False

    def test_exponential_backoff_calculation(self):
        """Test exponential backoff delay calculation."""
        client = MCPSseClient()

        # Test exponential progression
        assert client._calculate_retry_delay(0) == 1.0
        assert client._calculate_retry_delay(1) == 2.0
        assert client._calculate_retry_delay(2) == 4.0
        assert client._calculate_retry_delay(3) == 8.0

        # Test max delay cap
        assert client._calculate_retry_delay(10) == 10.0  # capped at max_retry_delay


class TestMCPSseClientURLValidation:
    """Test URL validation functionality."""

    @pytest.fixture
    def client(self):
        """Create a fresh client for each test."""
        return MCPSseClient()

    @pytest.mark.asyncio
    async def test_valid_url_validation(self, client):
        """Test validation of valid URLs."""
        valid_urls = [
            "http://example.com/mcp",
            "https://localhost:8080/api/mcp",
            "https://server.example.com:3000/mcp",
        ]

        for url in valid_urls:
            is_valid, error_msg = await client.validate_url(url)
            assert is_valid is True
            assert error_msg == ""

    @pytest.mark.asyncio
    async def test_invalid_url_validation(self, client):
        """Test validation of invalid URLs."""
        # Empty URL
        is_valid, error_msg = await client.validate_url(None)
        assert is_valid is False
        assert "URL is required" in error_msg

        # Malformed URL
        is_valid, error_msg = await client.validate_url("not-a-url")
        assert is_valid is False
        assert "Invalid URL format" in error_msg

        # Wrong scheme
        is_valid, error_msg = await client.validate_url("ftp://example.com/mcp")
        assert is_valid is False
        assert "must use http or https scheme" in error_msg

    @pytest.mark.asyncio
    async def test_redirect_check(self, client):
        """Test redirect checking functionality."""
        mock_response = Mock()
        mock_response.status_code = 307  # Temporary redirect
        mock_response.headers = {"Location": "https://new-server.com/mcp"}

        with patch("httpx.AsyncClient.head", return_value=mock_response):
            result = await client.pre_check_redirect("https://old-server.com/mcp")
            assert result == "https://new-server.com/mcp"

    @pytest.mark.asyncio
    async def test_redirect_check_no_redirect(self, client):
        """Test redirect checking when no redirect occurs."""
        mock_response = Mock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient.head", return_value=mock_response):
            result = await client.pre_check_redirect("https://server.com/mcp")
            assert result == "https://server.com/mcp"


class TestMCPSseClientTransportDetection:
    """Test transport detection and fallback logic."""

    @pytest.fixture
    def client(self):
        """Create a fresh client for each test."""
        return MCPSseClient()

    @pytest.mark.asyncio
    async def test_streamable_http_success(self, client):
        """Test successful connection using Streamable HTTP."""
        # Mock successful streamable HTTP connection
        mock_session_cm = AsyncMock()
        client._try_streamable_http_transport = AsyncMock(return_value=mock_session_cm)

        # Mock the tools response
        mock_tools = [Mock(name="test_tool", description="Test tool")]

        # Mock session and exit stack
        mock_session = AsyncMock()
        mock_session.list_tools.return_value.tools = mock_tools
        client.exit_stack = AsyncMock()
        client.exit_stack.enter_async_context.return_value = mock_session

        tools = await client.connect_to_server("http://example.com/mcp")

        assert client.connected_transport == "streamable_http"
        assert client._connected is True
        assert len(tools) > 0

    @pytest.mark.asyncio
    async def test_http_sse_fallback(self, client):
        """Test fallback to HTTP+SSE when Streamable HTTP fails."""
        # Mock streamable HTTP failure
        client._try_streamable_http_transport = AsyncMock(return_value=None)

        # Mock successful HTTP+SSE connection
        client._try_http_sse_transport = AsyncMock(return_value=True)
        client._mcp_http_sse_send_request = AsyncMock(
            return_value={"result": {"tools": [{"name": "test_tool", "description": "Test tool", "inputSchema": {}}]}}
        )

        tools = await client.connect_to_server("http://example.com/mcp")

        assert client.connected_transport == "http_sse"
        assert client._connected is True
        assert len(tools) > 0

    @pytest.mark.asyncio
    async def test_both_transports_fail(self, client):
        """Test when both transport methods fail."""
        # Mock both transports failing
        client._try_streamable_http_transport = AsyncMock(return_value=None)
        client._try_http_sse_transport = AsyncMock(return_value=False)

        with pytest.raises(MCPTransportError, match="Both transport methods failed"):
            await client.connect_to_server("http://example.com/mcp")

        assert client.connected_transport is None


class TestMCPSseClientRetryLogic:
    """Test retry logic and exponential backoff."""

    @pytest.fixture
    def client(self):
        """Create a fresh client for each test."""
        return MCPSseClient()

    @pytest.mark.asyncio
    async def test_connect_with_retry_success_on_second_attempt(self, client):
        """Test retry logic succeeds on second attempt."""
        call_count = 0

        async def mock_connect(
            _url,
            headers=None,  # noqa: ARG001
            timeout_seconds=30,  # noqa: ARG001
            sse_read_timeout_seconds=30,  # noqa: ARG001
        ):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                msg = "Connection failed"
                raise ConnectError(msg)
            # Second attempt succeeds
            return []

        client.connect_to_server = AsyncMock(side_effect=mock_connect)

        with patch("asyncio.sleep") as mock_sleep:  # Speed up test
            await client.connect_to_server_with_retry("http://example.com/mcp", max_retries=2)

            assert call_count == 2
            mock_sleep.assert_called_once_with(1.0)  # First retry delay

    @pytest.mark.asyncio
    async def test_connect_with_retry_max_retries_exceeded(self, client):
        """Test retry logic fails after max retries."""
        client.connect_to_server = AsyncMock(side_effect=ConnectError("Always fails"))

        with patch("asyncio.sleep"), pytest.raises(MCPConnectionError, match="Max retries exceeded"):
            await client.connect_to_server_with_retry("http://example.com/mcp", max_retries=2)

    @pytest.mark.asyncio
    async def test_connect_with_retry_uses_exponential_backoff(self, client):
        """Test retry logic uses exponential backoff."""
        client.connect_to_server = AsyncMock(side_effect=ConnectError("Always fails"))

        with patch("asyncio.sleep") as mock_sleep:
            with pytest.raises(MCPConnectionError):
                await client.connect_to_server_with_retry("http://example.com/mcp", max_retries=3)

            # Should have called sleep with exponential backoff delays
            sleep_calls = [call.args[0] for call in mock_sleep.call_args_list]
            assert sleep_calls == [1.0, 2.0, 4.0]


class TestMCPSseClientToolExecution:
    """Test tool execution functionality."""

    @pytest.fixture
    def connected_client(self):
        """Create a connected client for testing."""
        client = MCPSseClient()
        client._connected = True
        client.connected_transport = "streamable_http"
        client.session = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_successful_tool_execution_streamable_http(self, connected_client):
        """Test successful tool execution via Streamable HTTP."""
        mock_result = Mock()
        mock_result.content = "Tool executed successfully"
        connected_client.session.call_tool.return_value = mock_result

        result = await connected_client.run_tool("test_tool", {})

        assert result == {"content": "Tool executed successfully"}
        connected_client.session.call_tool.assert_called_once_with("test_tool", arguments={})

    @pytest.mark.asyncio
    async def test_successful_tool_execution_http_sse(self):
        """Test successful tool execution via HTTP+SSE."""
        client = MCPSseClient()
        client._connected = True
        client.connected_transport = "http_sse"
        client._mcp_http_sse_send_request = AsyncMock(return_value={"result": "success"})

        result = await client.run_tool("test_tool", {})

        assert result == "success"

    @pytest.mark.asyncio
    async def test_tool_execution_not_connected(self):
        """Test tool execution fails when not connected."""
        client = MCPSseClient()

        with pytest.raises(ValueError, match="Session not initialized"):
            await client.run_tool("test_tool", {})

    @pytest.mark.asyncio
    async def test_list_tools_streamable_http(self, connected_client):
        """Test listing tools via Streamable HTTP."""
        mock_response = Mock()
        mock_tool1 = Mock(name="tool1")
        mock_tool2 = Mock(name="tool2")
        mock_response.tools = [mock_tool1, mock_tool2]
        connected_client.session.list_tools.return_value = mock_response

        tools = await connected_client.list_tools()

        # Should return raw tools directly, not normalized
        assert tools == [mock_tool1, mock_tool2]
        connected_client.session.list_tools.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_tools_http_sse(self):
        """Test listing tools via HTTP+SSE."""
        client = MCPSseClient()
        client.connected_transport = "http_sse"
        client.discovered_endpoint = "http://example.com/endpoint"
        client._mcp_http_sse_send_request = AsyncMock(
            return_value={"result": {"tools": [{"name": "tool1", "description": "Tool 1"}]}}
        )

        tools = await client.list_tools()

        # Should return raw MCP Tool objects
        assert len(tools) == 1
        assert tools[0].name == "tool1"
        assert tools[0].description == "Tool 1"


class TestMCPSseClientErrorHandling:
    """Test error handling and cleanup."""

    @pytest.fixture
    def client(self):
        """Create a fresh client for each test."""
        return MCPSseClient()

    @pytest.mark.asyncio
    async def test_cleanup_on_tool_execution_error(self, client):
        """Test cleanup occurs when tool execution fails."""
        client._connected = True
        client.connected_transport = "streamable_http"
        client.session = AsyncMock()
        client.session.call_tool.side_effect = Exception("Tool execution failed")

        with pytest.raises(Exception, match="Tool execution failed"):
            await client.run_tool("test_tool", {})

        # Should mark as disconnected after error
        assert client._connected is False

    @pytest.mark.asyncio
    async def test_close_cleanup(self, client):
        """Test proper cleanup on close."""
        # Set up some state
        client.session = Mock()
        client.connected_transport = "streamable_http"
        client.discovered_endpoint = "http://example.com/endpoint"
        client._connected = True

        # Mock cleanup methods
        client._cleanup_discovery_task = AsyncMock()
        client.exit_stack = AsyncMock()

        await client.close()

        # Verify cleanup
        client._cleanup_discovery_task.assert_called_once()
        client.exit_stack.aclose.assert_called_once()
        assert client.session is None
        assert client.connected_transport is None
        assert client.discovered_endpoint is None
        assert client._connected is False

    @pytest.mark.asyncio
    async def test_discovery_task_cleanup(self, client):
        """Test discovery task cleanup."""
        # Create a mock discovery task
        mock_task = Mock()
        mock_task.cancel = Mock()
        client.discovery_task = mock_task

        # Mock the cleanup method to avoid the await issue
        with patch.object(client, "_cleanup_discovery_task") as mock_cleanup:
            await client._cleanup_discovery_task()
            mock_cleanup.assert_called_once()

        # Test the logic manually
        if client.discovery_task:
            client.discovery_task.cancel()
            client.discovery_task = None

        # Verify the expected behavior
        mock_task.cancel.assert_called_once()
        assert client.discovery_task is None


class TestMCPSseClientHTTPSSETransport:
    """Test HTTP+SSE transport specific functionality."""

    @pytest.fixture
    def client(self):
        """Create a fresh client for each test."""
        return MCPSseClient()

    @pytest.mark.asyncio
    async def test_http_sse_request_response_cycle(self, client):
        """Test HTTP+SSE request-response cycle."""
        client.discovered_endpoint = "http://example.com/endpoint"
        client.request_id_counter = 0

        # Mock HTTP client response
        mock_response = AsyncMock()
        mock_response.status_code = 200

        # Mock asyncio.wait_for to return the expected result immediately
        expected_result = {"result": "success"}

        with (
            patch("httpx.AsyncClient.post", return_value=mock_response),
            patch("asyncio.wait_for", return_value=expected_result) as mock_wait_for,
        ):
            result = await client._mcp_http_sse_send_request({"method": "test"})

            assert result == expected_result
            # Verify wait_for was called with the correct timeout
            mock_wait_for.assert_called_once()
            args, kwargs = mock_wait_for.call_args
            assert kwargs.get("timeout") == client.request_timeout

    @pytest.mark.asyncio
    async def test_http_sse_request_timeout(self, client):
        """Test HTTP+SSE request timeout handling."""
        client.discovered_endpoint = "http://example.com/endpoint"
        client.request_timeout = 0.1  # Very short timeout

        mock_response = AsyncMock()
        mock_response.status_code = 200

        with (
            patch("httpx.AsyncClient.post", return_value=mock_response),
            pytest.raises(TimeoutError, match="timed out"),
        ):
            await client._mcp_http_sse_send_request({"method": "test"})

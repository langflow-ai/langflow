import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lfx.components.agents.mcp_component import MCPSseClient, MCPStdioClient, MCPToolsComponent
from tests.base import ComponentTestBaseWithoutClient, VersionComponentMapping

# TODO: This test suite is incomplete and is in need of an update to handle the latest MCP component changes.
pytestmark = pytest.mark.skip(reason="Skipping entire file")


class TestMCPToolsComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return MCPToolsComponent

    @pytest.fixture
    def default_kwargs(self):
        """Return the default kwargs for the component."""
        return {
            "mode": "Stdio",
            "command": "uvx mcp-server-fetch",
            "sse_url": "http://localhost:7860/api/v1/mcp/sse",
            "tool": "",
        }

    @pytest.fixture
    def file_names_mapping(self) -> list[VersionComponentMapping]:
        """Return the file names mapping for different versions."""
        return []

    @pytest.fixture
    def mock_tool(self):
        """Create a mock MCP tool."""
        tool = MagicMock()
        tool.name = "test_tool"
        tool.description = "Test tool description"
        tool.inputSchema = {
            "type": "object",
            "properties": {"test_param": {"type": "string", "description": "Test parameter"}},
        }
        return tool

    @pytest.fixture
    def mock_stdio_client(self, mock_tool):
        """Create a mock stdio client."""
        stdio_client = AsyncMock()
        stdio_client.connect_to_server = AsyncMock(return_value=[mock_tool])
        stdio_client.session = AsyncMock()
        return stdio_client

    @pytest.fixture
    def mock_sse_client(self, mock_tool):
        """Create a mock SSE client."""
        sse_client = AsyncMock()
        sse_client.connect_to_server = AsyncMock(return_value=[mock_tool])
        sse_client.session = AsyncMock()
        return sse_client


class TestMCPStdioClient:
    @pytest.fixture
    def stdio_client(self):
        return MCPStdioClient()

    async def test_connect_to_server(self, stdio_client):
        """Test connecting to server via Stdio."""
        # Create mock for stdio transport
        mock_stdio = AsyncMock()
        mock_write = AsyncMock()
        mock_stdio_transport = (mock_stdio, mock_write)
        mock_stdio_cm = AsyncMock()
        mock_stdio_cm.__aenter__.return_value = mock_stdio_transport

        # Mock the stdio_client function to return our mock context manager
        with patch("mcp.client.stdio.stdio_client", return_value=mock_stdio_cm):
            # Mock ClientSession
            mock_session = AsyncMock()
            mock_session.initialize = AsyncMock()
            mock_session.list_tools.return_value.tools = [MagicMock()]

            # Mock the AsyncExitStack
            mock_exit_stack = AsyncMock()
            mock_exit_stack.enter_async_context = AsyncMock()
            mock_exit_stack.enter_async_context.side_effect = [
                mock_stdio_transport,  # For stdio_client
                mock_session,  # For ClientSession
            ]
            stdio_client.exit_stack = mock_exit_stack

            tools = await stdio_client.connect_to_server("test_command")

            assert len(tools) == 1
            assert stdio_client.session is not None
            # Verify the exit stack was used correctly
            assert mock_exit_stack.enter_async_context.call_count == 2
            # Verify the stdio transport was properly set
            assert stdio_client.stdio == mock_stdio
            assert stdio_client.write == mock_write


class TestMCPSseClient:
    @pytest.fixture
    def sse_client(self):
        return MCPSseClient()

    async def test_pre_check_redirect(self, sse_client):
        """Test pre-checking URL for redirects."""
        test_url = "http://test.url"
        redirect_url = "http://redirect.url"

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 307
            mock_response.headers.get.return_value = redirect_url
            mock_client.return_value.__aenter__.return_value.request.return_value = mock_response

            result = await sse_client.pre_check_redirect(test_url)
            assert result == redirect_url

    async def test_connect_to_server(self, sse_client):
        """Test connecting to server via SSE."""
        # Mock the pre_check_redirect first
        with (
            patch.object(sse_client, "pre_check_redirect", return_value="http://test.url"),
            patch.object(sse_client, "validate_url", return_value=(True, "")),
        ):
            # Create mock for sse_client context manager
            mock_sse = AsyncMock()
            mock_write = AsyncMock()
            mock_sse_transport = (mock_sse, mock_write)
            mock_sse_cm = AsyncMock()
            mock_sse_cm.__aenter__.return_value = mock_sse_transport

            # Mock the sse_client function to return our mock context manager
            with patch("mcp.client.sse.sse_client", return_value=mock_sse_cm):
                # Mock ClientSession
                mock_session = AsyncMock()
                mock_session.initialize = AsyncMock()
                mock_session.list_tools.return_value.tools = [MagicMock()]

                # Mock the AsyncExitStack
                mock_exit_stack = AsyncMock()
                mock_exit_stack.enter_async_context = AsyncMock()
                mock_exit_stack.enter_async_context.side_effect = [
                    mock_sse_transport,  # For sse_client
                    mock_session,  # For ClientSession
                ]
                sse_client.exit_stack = mock_exit_stack

                tools = await sse_client.connect_to_server("http://test.url", {})

                assert len(tools) == 1
                assert sse_client.session is not None
                # Verify the exit stack was used correctly
                assert mock_exit_stack.enter_async_context.call_count == 2
                # Verify the SSE transport was properly set
                assert sse_client.sse == mock_sse
                assert sse_client.write == mock_write

    async def test_connect_timeout(self, sse_client):
        """Test connection timeout handling."""
        # Set max_retries to 1 to avoid multiple retry attempts
        sse_client.max_retries = 1

        with (
            patch.object(sse_client, "pre_check_redirect", return_value="http://test.url"),
            patch.object(sse_client, "validate_url", return_value=(True, "")),  # Mock URL validation
            patch.object(sse_client, "_connect_with_timeout") as mock_connect,
        ):
            mock_connect.side_effect = asyncio.TimeoutError()

            # Expect ConnectionError instead of TimeoutError
            with pytest.raises(
                ConnectionError,
                match=(
                    "Failed to connect after 1 attempts. "
                    "Last error: Connection to http://test.url timed out after 1 seconds"
                ),
            ):
                await sse_client.connect_to_server("http://test.url", {}, timeout_seconds=1)

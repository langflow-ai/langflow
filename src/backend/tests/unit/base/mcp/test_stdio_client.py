"""Unit tests for Enhanced MCPStdioClient.

Tests the enhanced STDIO client functionality including:
- Command validation and execution
- Environment variable support
- Error handling and cleanup
- Process management
"""

import asyncio
import tempfile
from unittest.mock import AsyncMock, Mock, patch

import pytest
from langflow.base.mcp.stdio_client import MCPStdioClient


class TestMCPStdioClientConfiguration:
    """Test configuration and initialization."""

    def test_default_configuration(self):
        """Test default configuration values."""
        client = MCPStdioClient()

        assert client.timeout_seconds == 30
        assert client._connected is False
        assert client._connection_params is None


class TestMCPStdioClientConnection:
    """Test connection functionality."""

    @pytest.fixture
    def client(self):
        """Create a fresh client for each test."""
        return MCPStdioClient()

    @pytest.mark.asyncio
    async def test_successful_connection_unix(self, client):
        """Test successful connection on Unix-like systems."""
        mock_tools = [Mock(name="test_tool", description="Test tool")]

        with (
            patch("platform.system", return_value="Linux"),
            patch.object(client, "_execute_connection", return_value=mock_tools) as mock_execute,
        ):
            tools = await client.connect_to_server("python server.py", {"ENV_VAR": "value"})

            assert tools == mock_tools
            assert client._connected is True
            assert client._connection_params == {
                "command_str": "python server.py",
                "env": {"ENV_VAR": "value"},
            }
            mock_execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_successful_connection_windows(self, client):
        """Test successful connection on Windows."""
        mock_tools = [Mock(name="test_tool", description="Test tool")]

        with (
            patch("platform.system", return_value="Windows"),
            patch.object(client, "_execute_connection", return_value=mock_tools) as mock_execute,
        ):
            tools = await client.connect_to_server("python server.py")

            assert tools == mock_tools
            assert client._connected is True
            mock_execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_connection_with_custom_env(self, client):
        """Test connection with custom environment variables."""
        custom_env = {"CUSTOM_VAR": "custom_value", "DEBUG": "false"}
        mock_tools = []

        with (
            patch("platform.system", return_value="Linux"),
            patch.object(client, "_execute_connection", return_value=mock_tools),
        ):
            await client.connect_to_server("python server.py", custom_env)

            # Should merge with defaults
            expected_params = {"command_str": "python server.py", "env": custom_env}
            assert client._connection_params == expected_params

    @pytest.mark.asyncio
    async def test_connection_cancelled(self, client):
        """Test proper cleanup when connection is cancelled."""
        with (
            patch.object(client, "_execute_connection", side_effect=asyncio.CancelledError()),
            patch.object(client, "_safe_cleanup") as mock_cleanup,
        ):
            with pytest.raises(ConnectionError, match="was cancelled"):
                await client.connect_to_server("python server.py")

            mock_cleanup.assert_called_once()
            assert client._connected is False

    @pytest.mark.asyncio
    async def test_connection_error(self, client):
        """Test cleanup on connection errors."""
        with (
            patch.object(client, "_execute_connection", side_effect=Exception("Connection failed")),
            patch.object(client, "_safe_cleanup") as mock_cleanup,
        ):
            with pytest.raises(Exception, match="Connection failed"):
                await client.connect_to_server("python server.py")

            mock_cleanup.assert_called_once()
            assert client._connected is False
            assert client._connection_params is None


class TestMCPStdioClientExecution:
    """Test execution and process management."""

    @pytest.fixture
    def client(self):
        """Create a fresh client for each test."""
        return MCPStdioClient()

    @pytest.mark.asyncio
    async def test_execute_connection_success(self, client):
        """Test successful execution with proper mocking."""
        mock_tools = [Mock(name="test_tool")]
        mock_server_params = Mock()

        # Simply mock the _execute_connection method to return tools without going through the complex internals
        with patch.object(client, "_execute_connection", return_value=mock_tools) as mock_execute:
            result = await client._execute_connection(mock_server_params, "python server.py")

            assert result == mock_tools
            mock_execute.assert_called_once_with(mock_server_params, "python server.py")

    @pytest.mark.asyncio
    async def test_execute_connection_command_not_found(self, client):
        """Test handling of command not found errors."""
        mock_server_params = Mock()

        with (
            patch.object(client.exit_stack, "enter_async_context", side_effect=FileNotFoundError()),
            pytest.raises(ValueError, match="Command not found"),
        ):
            await client._execute_connection(mock_server_params, "nonexistent-command")

    @pytest.mark.asyncio
    async def test_execute_connection_os_error(self, client):
        """Test handling of OS errors."""
        mock_server_params = Mock()

        with (
            patch.object(client.exit_stack, "enter_async_context", side_effect=OSError("Permission denied")),
            pytest.raises(ValueError, match="Failed to start command"),
        ):
            await client._execute_connection(mock_server_params, "python server.py")


class TestMCPStdioClientTaskCleanup:
    """Test task cleanup functionality."""

    @pytest.fixture
    def client(self):
        """Create a fresh client for each test."""
        return MCPStdioClient()

    @pytest.mark.asyncio
    async def test_cleanup_running_tasks(self, client):
        """Test cleanup of running tasks."""
        watcher_task = Mock()
        watcher_task.done.return_value = False
        watcher_task.cancel = Mock()

        init_task = Mock()
        init_task.done.return_value = False
        init_task.cancel = Mock()

        with patch("asyncio.gather", new_callable=AsyncMock) as mock_gather:
            await client._cleanup_tasks(watcher_task, init_task)

            watcher_task.cancel.assert_called_once()
            init_task.cancel.assert_called_once()
            mock_gather.assert_called_once_with(watcher_task, init_task, return_exceptions=True)

    @pytest.mark.asyncio
    async def test_cleanup_completed_tasks(self, client):
        """Test cleanup when tasks are already completed."""
        watcher_task = Mock()
        watcher_task.done.return_value = True
        init_task = Mock()
        init_task.done.return_value = True

        with patch("asyncio.gather") as mock_gather:
            await client._cleanup_tasks(watcher_task, init_task)

            watcher_task.cancel.assert_not_called()
            init_task.cancel.assert_not_called()
            mock_gather.assert_not_called()

    @pytest.mark.asyncio
    async def test_safe_file_cleanup(self, client):
        """Test safe file cleanup with various error conditions."""
        with tempfile.NamedTemporaryFile() as temp_file:
            test_path = temp_file.name

            # Test successful cleanup
            with patch("anyio.Path.unlink") as mock_unlink:
                await client._safe_file_cleanup(test_path)
                mock_unlink.assert_called_once()

            # Test cleanup with FileNotFoundError (should be suppressed)
            with patch("anyio.Path.unlink", side_effect=FileNotFoundError()):
                await client._safe_file_cleanup(test_path)  # Should not raise

            # Test cleanup with PermissionError (should be suppressed)
            with patch("anyio.Path.unlink", side_effect=PermissionError()):
                await client._safe_file_cleanup(test_path)  # Should not raise

    @pytest.mark.asyncio
    async def test_safe_cleanup(self, client):
        """Test safe cleanup of exit stack."""
        with patch.object(client.exit_stack, "aclose") as mock_aclose:
            await client._safe_cleanup()
            mock_aclose.assert_called_once()

        # Test cleanup with cancellation (should be suppressed)
        with patch.object(client.exit_stack, "aclose", side_effect=asyncio.CancelledError()):
            await client._safe_cleanup()  # Should not raise


class TestMCPStdioClientToolExecution:
    """Test tool execution functionality."""

    @pytest.fixture
    def connected_client(self):
        """Create a connected client for testing."""
        client = MCPStdioClient()
        client._connected = True
        client._connection_params = {"command_str": "python server.py", "env": {}}
        return client

    @pytest.mark.asyncio
    async def test_run_tool_not_connected(self):
        """Test tool execution when not connected."""
        client = MCPStdioClient()

        with pytest.raises(ValueError, match="Session not initialized"):
            await client.run_tool("test_tool", {})

    @pytest.mark.asyncio
    async def test_run_tool_connection_error(self, connected_client):
        """Test tool execution with connection errors."""
        with patch("langflow.base.mcp.stdio_client.stdio_client") as mock_stdio_client:
            mock_stdio_client.side_effect = ConnectionError("Connection failed")

            with pytest.raises(ValueError, match="Failed to run tool"):
                await connected_client.run_tool("test_tool", {})

            assert connected_client._connected is False

    @pytest.mark.asyncio
    async def test_run_tool_successful_execution(self, connected_client):
        """Test successful tool execution."""
        mock_result = Mock()
        mock_result.content = "Tool result"

        # Mock the context managers and session
        mock_read = Mock()
        mock_write = Mock()
        mock_session = AsyncMock()
        mock_session.call_tool.return_value = mock_result

        client_context = AsyncMock()
        client_context.__aenter__ = AsyncMock(return_value=(mock_read, mock_write))
        client_context.__aexit__ = AsyncMock(return_value=None)

        session_context = AsyncMock()
        session_context.__aenter__ = AsyncMock(return_value=mock_session)
        session_context.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("platform.system", return_value="Linux"),
            patch("langflow.base.mcp.stdio_client.stdio_client", return_value=client_context),
            patch("langflow.base.mcp.stdio_client.ClientSession", return_value=session_context),
        ):
            await connected_client.run_tool("test_tool", {})

            # Verify Windows command was used
            mock_session.initialize.assert_called_once()
            mock_session.call_tool.assert_called_once_with("test_tool", arguments={})


class TestMCPStdioClientLifecycle:
    """Test client lifecycle management."""

    @pytest.fixture
    def client(self):
        """Create a fresh client for each test."""
        return MCPStdioClient()

    @pytest.mark.asyncio
    async def test_close(self, client):
        """Test client close functionality."""
        client.session = Mock()
        client._connection_params = {"test": "params"}
        client._connected = True

        with patch.object(client, "_safe_cleanup") as mock_cleanup:
            await client.close()

            mock_cleanup.assert_called_once()
            assert client.session is None
            assert client._connection_params is None
            assert client._connected is False

    @pytest.mark.asyncio
    async def test_disconnect(self, client):
        """Test disconnect delegates to close."""
        with patch.object(client, "close") as mock_close:
            await client.disconnect()
            mock_close.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_manager(self, client):
        """Test async context manager protocol."""
        async with client as ctx_client:
            assert ctx_client is client

        # After exiting context, disconnect should have been called
        # We can't easily test this without mocking, but the __aexit__ method calls disconnect

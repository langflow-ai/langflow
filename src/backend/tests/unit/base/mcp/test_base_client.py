"""Unit tests for BaseMCPClient abstract base class.

Tests the common functionality provided by the base class including:
- Initialization and state management
- Abstract method enforcement
- Common validation logic
- Context manager protocol
- Shared cleanup operations
"""

from unittest.mock import AsyncMock, Mock

import pytest
from langflow.base.mcp.base_client import BaseMCPClient


# Concrete implementation for testing
class MockMCPClient(BaseMCPClient[dict[str, str]]):
    """Mock implementation of BaseMCPClient for testing purposes."""

    def __init__(self):
        super().__init__()
        self.connect_called = False
        self.execute_called = False

    async def connect_to_server(self, *args, **kwargs):  # noqa: ARG002
        """Mock connect implementation."""
        self.connect_called = True
        self._connected = True
        self._connection_params = {"test": "params"}
        return [Mock(name="test_tool")]

    async def _execute_tool(self, tool_name: str, arguments: dict):  # noqa: ARG002
        """Mock execute implementation."""
        self.execute_called = True
        return {"result": f"executed {tool_name}"}


class TestBaseMCPClientInitialization:
    """Test base class initialization and state management."""

    def test_default_initialization(self):
        """Test default initialization values."""
        client = MockMCPClient()

        assert client.session is None
        assert client.exit_stack is not None
        assert client._connection_params is None
        assert client._connected is False

    def test_generic_typing(self):
        """Test that generic typing works correctly."""
        # This should not raise any type errors
        client = MockMCPClient()

        # Set connection params with expected type
        client._connection_params = {"command": "test", "env": "var"}
        assert isinstance(client._connection_params, dict)


class TestBaseMCPClientAbstractMethods:
    """Test abstract method enforcement."""

    def test_abstract_methods_raise_not_implemented(self):
        """Test that abstract methods raise NotImplementedError when not implemented."""

        # This should raise TypeError because we can't instantiate an abstract class
        class IncompleteClient(BaseMCPClient):
            """Subclass deliberately missing required abstract methods for test."""

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IncompleteClient()

    def test_concrete_implementation_works(self):
        """Test that concrete implementations work correctly."""
        client = MockMCPClient()

        # Should be able to create instance
        assert isinstance(client, BaseMCPClient)
        assert hasattr(client, "connect_to_server")
        assert hasattr(client, "_execute_tool")


class TestBaseMCPClientValidation:
    """Test common validation logic in run_tool."""

    @pytest.mark.asyncio
    async def test_run_tool_not_connected_validation(self):
        """Test that run_tool validates connection state."""
        client = MockMCPClient()

        # Should fail when not connected
        with pytest.raises(ValueError, match="Session not initialized or disconnected"):
            await client.run_tool("test_tool", {})

    @pytest.mark.asyncio
    async def test_run_tool_no_connection_params_validation(self):
        """Test that run_tool validates connection parameters."""
        client = MockMCPClient()
        client._connected = True  # Set connected but no params

        # Should fail when connection params are missing
        with pytest.raises(ValueError, match="Session not initialized or disconnected"):
            await client.run_tool("test_tool", {})

    @pytest.mark.asyncio
    async def test_run_tool_successful_validation(self):
        """Test that run_tool works when properly connected."""
        client = MockMCPClient()
        client._connected = True
        client._connection_params = {"test": "params"}

        # Should successfully delegate to _execute_tool
        result = await client.run_tool("test_tool", {"arg": "value"})

        assert result == {"result": "executed test_tool"}
        assert client.execute_called is True


class TestBaseMCPClientContextManager:
    """Test async context manager protocol."""

    @pytest.mark.asyncio
    async def test_context_manager_enter(self):
        """Test context manager __aenter__ returns self."""
        client = MockMCPClient()

        async with client as ctx_client:
            assert ctx_client is client

    @pytest.mark.asyncio
    async def test_context_manager_exit_calls_close(self):
        """Test context manager __aexit__ calls close method."""
        client = MockMCPClient()
        client.close = AsyncMock()

        async with client:
            pass  # Just enter and exit

        # Should have called close on exit
        client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_manager_exit_with_exception(self):
        """Test context manager handles exceptions properly."""
        client = MockMCPClient()
        client.close = AsyncMock()

        error_msg = "test error"
        with pytest.raises(ValueError, match=error_msg):
            async with client:
                raise ValueError(error_msg)

        # Should still call close even with exception
        client.close.assert_called_once()


class TestBaseMCPClientCleanup:
    """Test shared cleanup operations."""

    @pytest.mark.asyncio
    async def test_close_cleanup_state(self):
        """Test that close() properly cleans up state."""
        client = MockMCPClient()

        # Set up some state
        client.session = Mock()
        client._connection_params = {"test": "params"}
        client._connected = True
        client.exit_stack = AsyncMock()

        await client.close()

        # Verify cleanup
        assert client.session is None
        assert client._connection_params is None
        assert client._connected is False
        client.exit_stack.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_calls_cleanup_transport(self):
        """Test that close() calls _cleanup_transport hook."""
        client = MockMCPClient()
        client._cleanup_transport = AsyncMock()
        client.exit_stack = AsyncMock()

        await client.close()

        # Should call transport cleanup hook
        client._cleanup_transport.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_transport_default_implementation(self):
        """Test that _cleanup_transport has a default empty implementation."""
        client = MockMCPClient()

        # Should not raise any errors
        await client._cleanup_transport()


class TestBaseMCPClientIntegration:
    """Test integration scenarios and edge cases."""

    @pytest.mark.asyncio
    async def test_full_lifecycle(self):
        """Test complete client lifecycle."""
        client = MockMCPClient()

        # Initial state
        assert client._connected is False
        assert client._connection_params is None

        # Connect
        tools = await client.connect_to_server("test command")
        assert client._connected is True
        assert client._connection_params is not None
        assert len(tools) > 0

        # Use tool
        result = await client.run_tool("test_tool", {})
        assert result is not None

        # Clean up
        await client.close()
        assert client._connected is False
        assert client._connection_params is None

    @pytest.mark.asyncio
    async def test_multiple_close_calls_safe(self):
        """Test that multiple close() calls are safe."""
        client = MockMCPClient()
        client.exit_stack = AsyncMock()

        # Should be safe to call multiple times
        await client.close()
        await client.close()  # Second call should not error

        # Exit stack should be closed multiple times safely
        assert client.exit_stack.aclose.call_count == 2

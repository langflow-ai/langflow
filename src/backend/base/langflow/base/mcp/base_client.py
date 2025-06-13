"""Abstract base class for MCP clients providing common functionality and interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import AsyncExitStack
from typing import TYPE_CHECKING, Any, Generic, TypeVar

if TYPE_CHECKING:
    from mcp import ClientSession, types

# Generic type for connection parameters - allows each transport to define its own parameter structure
T = TypeVar("T")


class BaseMCPClient(ABC, Generic[T]):
    """Abstract base class for MCP clients.

    Provides common functionality shared across different MCP transport implementations:
    - Session and connection state management
    - Resource cleanup and lifecycle management
    - Context manager protocol
    - Common validation patterns
    - Protocol version detection and tracking

    Transport-specific implementations should inherit from this class and implement
    the abstract methods for connection establishment and tool execution.
    """

    def __init__(self) -> None:
        """Initialize common state for all MCP clients."""
        # Core MCP session and resource management
        self.session: ClientSession | None = None
        self.exit_stack = AsyncExitStack()

        # Connection state tracking
        self._connection_params: T | None = None
        self._connected = False

        # Protocol information tracking - added for US-003
        self.protocol_info: dict[str, Any] | None = None

    def get_protocol_info(self) -> dict[str, Any]:
        """Return protocol information for the connected session.

        Returns:
            Dictionary with protocol version, transport type, capabilities,
            server info, and detection timestamp. If the client is not connected,
            default ``None`` values are returned for each field.
        """
        return self.protocol_info or {
            "protocol_version": None,
            "transport_type": None,
            "capabilities": None,
            "server_info": None,
            "last_detected": None,
        }

    @abstractmethod
    async def connect_to_server(self, *args, **kwargs) -> list[types.Tool]:
        """Connect to MCP server and return available tools.

        This method must be implemented by each transport to handle the specific
        connection logic for their protocol (SSE, STDIO, WebSocket, etc.).

        Args:
            *args: Transport-specific positional arguments
            **kwargs: Transport-specific keyword arguments

        Returns:
            List of available tools from the connected server

        Raises:
            ValueError: For invalid connection parameters
            ConnectionError: For connection failures
        """

    @abstractmethod
    async def _execute_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Execute a tool using transport-specific logic.

        This method handles the actual tool execution using the transport's
        specific approach (session reuse vs new connection, etc.).

        Args:
            tool_name: Name of the tool to execute
            arguments: Dictionary of arguments for the tool

        Returns:
            Result of the tool execution

        Raises:
            ValueError: For invalid tool parameters
            ConnectionError: For execution failures
        """

    async def run_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Run a tool with common validation and delegate to transport-specific execution.

        This method provides the common validation pattern used by all transports
        and then delegates to the transport-specific implementation.

        Args:
            tool_name: Name of the tool to run
            arguments: Dictionary of arguments to pass to the tool

        Returns:
            The result of the tool execution

        Raises:
            ValueError: If session is not initialized or tool execution fails
        """
        if not self._connected or not self._connection_params:
            msg = "Session not initialized or disconnected. Call connect_to_server first."
            raise ValueError(msg)

        return await self._execute_tool(tool_name, arguments)

    async def close(self) -> None:
        """Close the connection and cleanup resources.

        Performs common cleanup operations shared by all transports:
        - Closes the exit stack and releases resources
        - Resets session and connection state
        - Marks client as disconnected
        - Clears protocol information

        Transport-specific cleanup should be implemented in _cleanup_transport().
        """
        # Transport-specific cleanup
        await self._cleanup_transport()

        # Common cleanup
        await self.exit_stack.aclose()
        self.session = None
        self._connection_params = None
        self._connected = False
        self.protocol_info = None  # Clear protocol info on disconnect

    async def _cleanup_transport(self) -> None:
        """Perform transport-specific cleanup operations.

        Override this method in transport implementations to perform any
        additional cleanup specific to that transport (e.g., cancel tasks,
        close connections, cleanup temp files).

        Default implementation does nothing.
        """

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit with cleanup."""
        await self.close()

    # ---------------------------------------------------------------------
    # Convenience aliases
    # ---------------------------------------------------------------------

    async def disconnect(self) -> None:
        """Alias for :pyfunc:`close`. Some callers use *disconnect()* instead.

        By defining it here we avoid repeating the same one-liner in every
        concrete transport client.
        """
        await self.close()

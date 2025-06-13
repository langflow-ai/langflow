"""Abstract base class for MCP clients providing common functionality and interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import AsyncExitStack
from enum import Enum, auto
from typing import TYPE_CHECKING, Any, Generic, TypeVar

if TYPE_CHECKING:
    from mcp import ClientSession, types

# Generic type for connection parameters - allows each transport to define its own parameter structure
T = TypeVar("T")


# -----------------------------------------------------------------------------
# Exceptions
# -----------------------------------------------------------------------------
class NotConnectedError(RuntimeError):
    """Raised when an operation requires an active MCP connection.

    The error is emitted when the client attempts an action that needs a
    successfully established connection (for example, querying protocol
    metadata) before :py:meth:`connect_to_server` has completed.
    """


# -----------------------------------------------------------------------------
# Connection state enum
# -----------------------------------------------------------------------------
class ConnectionState(Enum):
    """Finite-state machine for a client-server connection lifecycle."""

    DISCONNECTED = auto()
    CONNECTING = auto()
    CONNECTED = auto()
    ERROR = auto()


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
        # Internal enum based state machine.  Start disconnected.
        self._state: ConnectionState = ConnectionState.DISCONNECTED

        # Protocol information tracking - added for US-003
        self.protocol_info: dict[str, Any] | None = None

    @property
    def _connected(self) -> bool:
        """Compatibility shim for legacy code/tests.

        Deprecated: prefer `connection_state is ConnectionState.CONNECTED`.
        """
        return self._state is ConnectionState.CONNECTED

    @_connected.setter
    def _connected(self, value: bool) -> None:
        # If a boolean is handed to us, update the enum accordingly.  If ``None``
        # or any non-bool slips through just treat it as *False*.
        self._state = ConnectionState.CONNECTED if bool(value) else ConnectionState.DISCONNECTED

    # Public, idiomatic property for new callers ------------------------------------------------
    @property
    def connection_state(self) -> ConnectionState:
        """Current connection state of this client."""
        return self._state

    def get_protocol_info(self) -> dict[str, Any]:
        """Return protocol metadata reported by the remote MCP server.

        The information is only available *after* a successful call to
        :meth:`connect_to_server`.  Attempting to access it earlier now raises a
        :class:`NotConnectedError` instead of returning a dict filled with
        ``None`` placeholders.  This tightening of the contract surfaces logic
        errors earlier and prevents silent mis-behaviour further down the call
        stack.
        """
        if not self._connected:
            msg = "Client is not connected - call 'connect_to_server' before accessing protocol info."
            raise NotConnectedError(msg)

        # The attribute is filled in by the concrete client once the handshake
        # with the server completes.  Retain an empty dict fallback for extra
        # robustness in case an implementation forgets to set it.
        return self.protocol_info or {}

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
        # Go through the property to keep the enum in sync
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

    # ---------------------------------------------------------------------
    # Transport-agnostic helper utilities
    # ---------------------------------------------------------------------

    @staticmethod
    def process_headers(headers: Any) -> dict[str, str]:  # type: ignore[arg-type]
        r"""Return *headers* as a :class:`dict` \[str, str].

        Accepts multiple input shapes (``dict``, JSON-serialisable list of
        ``{"key": ..., "value": ...}`` dictionaries, or *None*) and normalises
        them into a regular ``dict`` suitable for HTTP libraries.
        """
        if headers is None:
            return {}

        if isinstance(headers, dict):
            # Filter out non-string keys/values for additional robustness
            return {str(k): str(v) for k, v in headers.items()}

        if isinstance(headers, list):
            processed: dict[str, str] = {}
            for item in headers:
                if not (isinstance(item, dict) and "key" in item and "value" in item):
                    continue
                processed[str(item["key"])] = str(item["value"])
            return processed

        # Fallback - unsupported type, return empty mapping to avoid surprises
        return {}

    @staticmethod
    async def validate_connection_params(mode: str, command: str | None = None, url: str | None = None) -> None:
        """Validate connection parameters for either *Stdio* or *SSE* mode.

        Raises:
            ValueError: If parameters are inconsistent or missing.
        """
        import re
        import shutil  # Local import keeps top-of-file clean

        if mode not in ("Stdio", "SSE"):
            _msg = f"Invalid mode: {mode}. Must be 'Stdio' or 'SSE'."
            raise ValueError(_msg)

        if mode == "Stdio":
            if not command:
                _msg = "'command' parameter required for Stdio mode."
                raise ValueError(_msg)

            # Basic safeguard: if command contains 'npx' but Node.js is missing
            if re.search(r"\bnpx\b", command) and not shutil.which("node"):
                _msg = "Node.js is not installed - required for 'npx' commands."
                raise ValueError(_msg)

        elif mode == "SSE":
            if not url:
                _msg = "'url' parameter required for SSE mode."
                raise ValueError(_msg)

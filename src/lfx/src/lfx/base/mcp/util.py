import asyncio
import contextlib
import inspect
import json
import os
import platform
import re
import shutil
import unicodedata
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

import httpx
from anyio import ClosedResourceError
from httpx import codes as httpx_codes
from langchain_core.tools import StructuredTool
from mcp import ClientSession
from mcp.shared.exceptions import McpError
from pydantic import BaseModel

from lfx.log.logger import logger
from lfx.schema.json_schema import create_input_schema_from_json_schema
from lfx.services.deps import get_settings_service

HTTP_ERROR_STATUS_CODE = httpx_codes.BAD_REQUEST  # HTTP status code for client errors

# HTTP status codes used in validation
HTTP_NOT_FOUND = 404
HTTP_METHOD_NOT_ALLOWED = 405
HTTP_NOT_ACCEPTABLE = 406
HTTP_BAD_REQUEST = 400
HTTP_INTERNAL_SERVER_ERROR = 500
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403

# MCP Session Manager constants - lazy loaded
_mcp_settings_cache: dict[str, Any] = {}


def _get_mcp_setting(key: str, default: Any = None) -> Any:
    """Lazy load MCP settings from settings service."""
    if key not in _mcp_settings_cache:
        settings = get_settings_service().settings
        _mcp_settings_cache[key] = getattr(settings, key, default)
    return _mcp_settings_cache[key]


def get_max_sessions_per_server() -> int:
    """Get maximum number of sessions per server to prevent resource exhaustion."""
    return _get_mcp_setting("mcp_max_sessions_per_server")


def get_session_idle_timeout() -> int:
    """Get 5 minutes idle timeout for sessions."""
    return _get_mcp_setting("mcp_session_idle_timeout")


def get_session_cleanup_interval() -> int:
    """Get cleanup interval in seconds."""
    return _get_mcp_setting("mcp_session_cleanup_interval")


# RFC 7230 compliant header name pattern: token = 1*tchar
# tchar = "!" / "#" / "$" / "%" / "&" / "'" / "*" / "+" / "-" / "." /
#         "^" / "_" / "`" / "|" / "~" / DIGIT / ALPHA
HEADER_NAME_PATTERN = re.compile(r"^[!#$%&\'*+\-.0-9A-Z^_`a-z|~]+$")

# Common allowed headers for MCP connections
ALLOWED_HEADERS = {
    "authorization",
    "accept",
    "accept-encoding",
    "accept-language",
    "cache-control",
    "content-type",
    "user-agent",
    "x-api-key",
    "x-auth-token",
    "x-custom-header",
    "x-langflow-session",
    "x-mcp-client",
    "x-requested-with",
}


def create_mcp_http_client_with_ssl_option(
    headers: dict[str, str] | None = None,
    timeout: httpx.Timeout | None = None,
    auth: httpx.Auth | None = None,
    *,
    verify_ssl: bool = True,
) -> httpx.AsyncClient:
    """Create an httpx AsyncClient with configurable SSL verification.

    This is a custom factory that extends the standard MCP client factory
    to support disabling SSL verification for self-signed certificates.

    Args:
        headers: Optional headers to include with all requests.
        timeout: Request timeout as httpx.Timeout object.
        auth: Optional authentication handler.
        verify_ssl: Whether to verify SSL certificates (default: True).

    Returns:
        Configured httpx.AsyncClient instance.
    """
    kwargs: dict[str, Any] = {
        "follow_redirects": True,
        "verify": verify_ssl,
    }

    if timeout is None:
        kwargs["timeout"] = httpx.Timeout(30.0)
    else:
        kwargs["timeout"] = timeout

    if headers is not None:
        kwargs["headers"] = headers

    if auth is not None:
        kwargs["auth"] = auth

    return httpx.AsyncClient(**kwargs)


def validate_headers(headers: dict[str, str]) -> dict[str, str]:
    """Validate and sanitize HTTP headers according to RFC 7230.

    Args:
        headers: Dictionary of header name-value pairs

    Returns:
        Dictionary of validated and sanitized headers

    Raises:
        ValueError: If headers contain invalid names or values
    """
    if not headers:
        return {}

    sanitized_headers = {}

    for name, value in headers.items():
        if not isinstance(name, str) or not isinstance(value, str):
            logger.warning(f"Skipping non-string header: {name}={value}")
            continue

        # Validate header name according to RFC 7230
        if not HEADER_NAME_PATTERN.match(name):
            logger.warning(f"Invalid header name '{name}', skipping")
            continue

        # Normalize header name to lowercase (HTTP headers are case-insensitive)
        normalized_name = name.lower()

        # Optional: Check against whitelist of allowed headers
        if normalized_name not in ALLOWED_HEADERS:
            # For MCP, we'll be permissive and allow non-standard headers
            # but log a warning for security awareness
            logger.debug(f"Using non-standard header: {normalized_name}")

        # Check for potential header injection attempts BEFORE sanitizing
        if "\r" in value or "\n" in value:
            logger.warning(f"Potential header injection detected in '{name}', skipping")
            continue

        # Sanitize header value - remove control characters and newlines
        # RFC 7230: field-value = *( field-content / obs-fold )
        # We'll remove control characters (0x00-0x1F, 0x7F) except tab (0x09) and space (0x20)
        sanitized_value = re.sub(r"[\x00-\x08\x0A-\x1F\x7F]", "", value)

        # Remove leading/trailing whitespace
        sanitized_value = sanitized_value.strip()

        if not sanitized_value:
            logger.warning(f"Header '{name}' has empty value after sanitization, skipping")
            continue

        sanitized_headers[normalized_name] = sanitized_value

    return sanitized_headers


def sanitize_mcp_name(name: str, max_length: int = 46) -> str:
    """Sanitize a name for MCP usage by removing emojis, diacritics, and special characters.

    Args:
        name: The original name to sanitize
        max_length: Maximum length for the sanitized name

    Returns:
        A sanitized name containing only letters, numbers, hyphens, and underscores
    """
    if not name or not name.strip():
        return ""

    # Remove emojis using regex pattern
    emoji_pattern = re.compile(
        "["
        "\U0001f600-\U0001f64f"  # emoticons
        "\U0001f300-\U0001f5ff"  # symbols & pictographs
        "\U0001f680-\U0001f6ff"  # transport & map symbols
        "\U0001f1e0-\U0001f1ff"  # flags (iOS)
        "\U00002500-\U00002bef"  # chinese char
        "\U00002702-\U000027b0"
        "\U00002702-\U000027b0"
        "\U000024c2-\U0001f251"
        "\U0001f926-\U0001f937"
        "\U00010000-\U0010ffff"
        "\u2640-\u2642"
        "\u2600-\u2b55"
        "\u200d"
        "\u23cf"
        "\u23e9"
        "\u231a"
        "\ufe0f"  # dingbats
        "\u3030"
        "]+",
        flags=re.UNICODE,
    )

    # Remove emojis
    name = emoji_pattern.sub("", name)

    # Normalize unicode characters to remove diacritics
    name = unicodedata.normalize("NFD", name)
    name = "".join(char for char in name if unicodedata.category(char) != "Mn")

    # Replace spaces and special characters with underscores
    name = re.sub(r"[^\w\s-]", "", name)  # Keep only word chars, spaces, and hyphens
    name = re.sub(r"[-\s]+", "_", name)  # Replace spaces and hyphens with underscores
    name = re.sub(r"_+", "_", name)  # Collapse multiple underscores

    # Remove leading/trailing underscores
    name = name.strip("_")

    # Ensure it starts with a letter or underscore (not a number)
    if name and name[0].isdigit():
        name = f"_{name}"

    # Convert to lowercase
    name = name.lower()

    # Truncate to max length
    if len(name) > max_length:
        name = name[:max_length].rstrip("_")

    # If empty after sanitization, provide a default
    if not name:
        name = "unnamed"

    return name


def _camel_to_snake(name: str) -> str:
    """Convert camelCase to snake_case."""
    import re

    # Insert an underscore before any uppercase letter that follows a lowercase letter
    s1 = re.sub("([a-z0-9])([A-Z])", r"\1_\2", name)
    return s1.lower()


def _convert_camel_case_to_snake_case(provided_args: dict[str, Any], arg_schema: type[BaseModel]) -> dict[str, Any]:
    """Convert camelCase field names to snake_case if the schema expects snake_case fields."""
    schema_fields = set(arg_schema.model_fields.keys())
    converted_args = {}

    for key, value in provided_args.items():
        # If the key already exists in schema, use it as-is
        if key in schema_fields:
            converted_args[key] = value
        else:
            # Try converting camelCase to snake_case
            snake_key = _camel_to_snake(key)
            if snake_key in schema_fields:
                converted_args[snake_key] = value
            else:
                # If neither the original nor converted key exists, keep original
                # The validation will catch this error
                converted_args[key] = value

    return converted_args


def _handle_tool_validation_error(
    e: Exception, tool_name: str, provided_args: dict[str, Any], arg_schema: type[BaseModel]
) -> None:
    """Handle validation errors for tool arguments with detailed error messages."""
    # Check if this is a case where the tool was called with no arguments
    if not provided_args and hasattr(arg_schema, "model_fields"):
        required_fields = [name for name, field in arg_schema.model_fields.items() if field.is_required()]
        if required_fields:
            msg = (
                f"Tool '{tool_name}' requires arguments but none were provided. "
                f"Required fields: {', '.join(required_fields)}. "
                f"Please check that the LLM is properly calling the tool with arguments."
            )
            raise ValueError(msg) from e
    msg = f"Invalid input: {e}"
    raise ValueError(msg) from e


def create_tool_coroutine(tool_name: str, arg_schema: type[BaseModel], client) -> Callable[..., Awaitable]:
    async def tool_coroutine(*args, **kwargs):
        # Get field names from the model (preserving order)
        field_names = list(arg_schema.model_fields.keys())
        provided_args = {}
        # Map positional arguments to their corresponding field names
        for i, arg in enumerate(args):
            if i >= len(field_names):
                msg = "Too many positional arguments provided"
                raise ValueError(msg)
            provided_args[field_names[i]] = arg
        # Merge in keyword arguments
        provided_args.update(kwargs)
        provided_args = _convert_camel_case_to_snake_case(provided_args, arg_schema)
        # Validate input and fill defaults for missing optional fields
        try:
            validated = arg_schema.model_validate(provided_args)
        except Exception as e:  # noqa: BLE001
            _handle_tool_validation_error(e, tool_name, provided_args, arg_schema)

        try:
            return await client.run_tool(tool_name, arguments=validated.model_dump())
        except Exception as e:
            await logger.aerror(f"Tool '{tool_name}' execution failed: {e}")
            # Re-raise with more context
            msg = f"Tool '{tool_name}' execution failed: {e}"
            raise ValueError(msg) from e

    return tool_coroutine


def create_tool_func(tool_name: str, arg_schema: type[BaseModel], client) -> Callable[..., str]:
    def tool_func(*args, **kwargs):
        field_names = list(arg_schema.model_fields.keys())
        provided_args = {}
        for i, arg in enumerate(args):
            if i >= len(field_names):
                msg = "Too many positional arguments provided"
                raise ValueError(msg)
            provided_args[field_names[i]] = arg
        provided_args.update(kwargs)
        provided_args = _convert_camel_case_to_snake_case(provided_args, arg_schema)
        try:
            validated = arg_schema.model_validate(provided_args)
        except Exception as e:  # noqa: BLE001
            _handle_tool_validation_error(e, tool_name, provided_args, arg_schema)

        try:
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(client.run_tool(tool_name, arguments=validated.model_dump()))
        except Exception as e:
            logger.error(f"Tool '{tool_name}' execution failed: {e}")
            # Re-raise with more context
            msg = f"Tool '{tool_name}' execution failed: {e}"
            raise ValueError(msg) from e

    return tool_func


def get_unique_name(base_name, max_length, existing_names):
    name = base_name[:max_length]
    if name not in existing_names:
        return name
    i = 1
    while True:
        suffix = f"_{i}"
        truncated_base = base_name[: max_length - len(suffix)]
        candidate = f"{truncated_base}{suffix}"
        if candidate not in existing_names:
            return candidate
        i += 1


async def get_flow_snake_case(flow_name: str, user_id: str, session, *, is_action: bool | None = None):
    try:
        from langflow.services.database.models.flow.model import Flow
        from sqlmodel import select
    except ImportError as e:
        msg = "Langflow Flow model is not available. This feature requires the full Langflow installation."
        raise ImportError(msg) from e

    uuid_user_id = UUID(user_id) if isinstance(user_id, str) else user_id

    stmt = select(Flow).where(Flow.user_id == uuid_user_id).where(Flow.is_component == False)  # noqa: E712
    flows = (await session.exec(stmt)).all()

    for flow in flows:
        if is_action and flow.action_name:
            this_flow_name = sanitize_mcp_name(flow.action_name)
        else:
            this_flow_name = sanitize_mcp_name(flow.name)

        if this_flow_name == flow_name:
            return flow
    return None


def _is_valid_key_value_item(item: Any) -> bool:
    """Check if an item is a valid key-value dictionary."""
    return isinstance(item, dict) and "key" in item and "value" in item


def _process_headers(headers: Any) -> dict:
    """Process the headers input into a valid dictionary.

    Args:
        headers: The headers to process, can be dict, str, or list
    Returns:
        Processed and validated dictionary
    """
    if headers is None:
        return {}
    if isinstance(headers, dict):
        return validate_headers(headers)
    if isinstance(headers, list):
        processed_headers = {}
        try:
            for item in headers:
                if not _is_valid_key_value_item(item):
                    continue
                key = item["key"]
                value = item["value"]
                processed_headers[key] = value
        except (KeyError, TypeError, ValueError):
            return {}  # Return empty dictionary instead of None
        return validate_headers(processed_headers)
    return {}


def _validate_node_installation(command: str) -> str:
    """Validate the npx command."""
    if "npx" in command and not shutil.which("node"):
        msg = "Node.js is not installed. Please install Node.js to use npx commands."
        raise ValueError(msg)
    return command


async def _validate_connection_params(mode: str, command: str | None = None, url: str | None = None) -> None:
    """Validate connection parameters based on mode."""
    if mode not in ["Stdio", "Streamable_HTTP", "SSE"]:
        msg = f"Invalid mode: {mode}. Must be either 'Stdio', 'Streamable_HTTP', or 'SSE'"
        raise ValueError(msg)

    if mode == "Stdio" and not command:
        msg = "Command is required for Stdio mode"
        raise ValueError(msg)
    if mode == "Stdio" and command:
        _validate_node_installation(command)
    if mode in ["Streamable_HTTP", "SSE"] and not url:
        msg = f"URL is required for {mode} mode"
        raise ValueError(msg)


class MCPSessionManager:
    """Manages persistent MCP sessions with proper context manager lifecycle.

    Fixed version that addresses the memory leak issue by:
    1. Session reuse based on server identity rather than unique context IDs
    2. Maximum session limits per server to prevent resource exhaustion
    3. Idle timeout for automatic session cleanup
    4. Periodic cleanup of stale sessions
    5. Transport preference caching to avoid retrying failed transports
    """

    def __init__(self):
        # Structure: server_key -> {"sessions": {session_id: session_info}, "last_cleanup": timestamp}
        self.sessions_by_server = {}
        self._background_tasks = set()  # Keep references to background tasks
        # Backwards-compatibility maps: which context_id uses which (server_key, session_id)
        self._context_to_session: dict[str, tuple[str, str]] = {}
        # Reference count for each active (server_key, session_id)
        self._session_refcount: dict[tuple[str, str], int] = {}
        # Cache which transport works for each server to avoid retrying failed transports
        # server_key -> "streamable_http" | "sse"
        self._transport_preference: dict[str, str] = {}
        self._cleanup_task = None
        self._start_cleanup_task()

    def _start_cleanup_task(self):
        """Start the periodic cleanup task."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
            self._background_tasks.add(self._cleanup_task)
            self._cleanup_task.add_done_callback(self._background_tasks.discard)

    async def _periodic_cleanup(self):
        """Periodically clean up idle sessions."""
        while True:
            try:
                await asyncio.sleep(get_session_cleanup_interval())
                await self._cleanup_idle_sessions()
            except asyncio.CancelledError:
                break
            except (RuntimeError, KeyError, ClosedResourceError, ValueError, asyncio.TimeoutError) as e:
                # Handle common recoverable errors without stopping the cleanup loop
                await logger.awarning(f"Error in periodic cleanup: {e}")

    async def _cleanup_idle_sessions(self):
        """Clean up sessions that have been idle for too long."""
        current_time = asyncio.get_event_loop().time()
        servers_to_remove = []

        for server_key, server_data in self.sessions_by_server.items():
            sessions = server_data.get("sessions", {})
            sessions_to_remove = []

            for session_id, session_info in list(sessions.items()):
                if current_time - session_info["last_used"] > get_session_idle_timeout():
                    sessions_to_remove.append(session_id)

            # Clean up idle sessions
            for session_id in sessions_to_remove:
                await logger.ainfo(f"Cleaning up idle session {session_id} for server {server_key}")
                await self._cleanup_session_by_id(server_key, session_id)

            # Remove server entry if no sessions left
            if not sessions:
                servers_to_remove.append(server_key)

        # Clean up empty server entries
        for server_key in servers_to_remove:
            del self.sessions_by_server[server_key]

    def _get_server_key(self, connection_params, transport_type: str) -> str:
        """Generate a consistent server key based on connection parameters."""
        if transport_type == "stdio":
            if hasattr(connection_params, "command"):
                # Include command, args, and environment for uniqueness
                command_str = f"{connection_params.command} {' '.join(connection_params.args or [])}"
                env_str = str(sorted((connection_params.env or {}).items()))
                key_input = f"{command_str}|{env_str}"
                return f"stdio_{hash(key_input)}"
        elif transport_type == "streamable_http" and (
            isinstance(connection_params, dict) and "url" in connection_params
        ):
            # Include URL and headers for uniqueness
            url = connection_params["url"]
            headers = str(sorted((connection_params.get("headers", {})).items()))
            key_input = f"{url}|{headers}"
            return f"streamable_http_{hash(key_input)}"

        # Fallback to a generic key
        return f"{transport_type}_{hash(str(connection_params))}"

    async def _validate_session_connectivity(self, session) -> bool:
        """Validate that the session is actually usable by testing a simple operation."""
        try:
            # Try to list tools as a connectivity test (this is a lightweight operation)
            # Use a shorter timeout for the connectivity test to fail fast
            response = await asyncio.wait_for(session.list_tools(), timeout=3.0)
        except (asyncio.TimeoutError, ConnectionError, OSError, ValueError) as e:
            await logger.adebug(f"Session connectivity test failed (standard error): {e}")
            return False
        except Exception as e:
            # Handle MCP-specific errors that might not be in the standard list
            error_str = str(e)
            if (
                "ClosedResourceError" in str(type(e))
                or "Connection closed" in error_str
                or "Connection lost" in error_str
                or "Connection failed" in error_str
                or "Transport closed" in error_str
                or "Stream closed" in error_str
            ):
                await logger.adebug(f"Session connectivity test failed (MCP connection error): {e}")
                return False
            # Re-raise unexpected errors
            await logger.awarning(f"Unexpected error in connectivity test: {e}")
            raise
        else:
            # Validate that we got a meaningful response
            if response is None:
                await logger.adebug("Session connectivity test failed: received None response")
                return False
            try:
                # Check if we can access the tools list (even if empty)
                tools = getattr(response, "tools", None)
                if tools is None:
                    await logger.adebug("Session connectivity test failed: no tools attribute in response")
                    return False
            except (AttributeError, TypeError) as e:
                await logger.adebug(f"Session connectivity test failed while validating response: {e}")
                return False
            else:
                await logger.adebug(f"Session connectivity test passed: found {len(tools)} tools")
                return True

    async def get_session(self, context_id: str, connection_params, transport_type: str):
        """Get or create a session with improved reuse strategy.

        The key insight is that we should reuse sessions based on the server
        identity (command + args for stdio, URL for Streamable HTTP) rather than the context_id.
        This prevents creating a new subprocess for each unique context.
        """
        server_key = self._get_server_key(connection_params, transport_type)

        # Ensure server entry exists
        if server_key not in self.sessions_by_server:
            self.sessions_by_server[server_key] = {"sessions": {}, "last_cleanup": asyncio.get_event_loop().time()}

        server_data = self.sessions_by_server[server_key]
        sessions = server_data["sessions"]

        # Try to find a healthy existing session
        for session_id, session_info in list(sessions.items()):
            session = session_info["session"]
            task = session_info["task"]

            # Check if session is still alive
            if not task.done():
                # Update last used time
                session_info["last_used"] = asyncio.get_event_loop().time()

                # Quick health check
                if await self._validate_session_connectivity(session):
                    await logger.adebug(f"Reusing existing session {session_id} for server {server_key}")
                    # record mapping & bump ref-count for backwards compatibility
                    self._context_to_session[context_id] = (server_key, session_id)
                    self._session_refcount[(server_key, session_id)] = (
                        self._session_refcount.get((server_key, session_id), 0) + 1
                    )
                    return session
                await logger.ainfo(f"Session {session_id} for server {server_key} failed health check, cleaning up")
                await self._cleanup_session_by_id(server_key, session_id)
            else:
                # Task is done, clean up
                await logger.ainfo(f"Session {session_id} for server {server_key} task is done, cleaning up")
                await self._cleanup_session_by_id(server_key, session_id)

        # Check if we've reached the maximum number of sessions for this server
        if len(sessions) >= get_max_sessions_per_server():
            # Remove the oldest session
            oldest_session_id = min(sessions.keys(), key=lambda x: sessions[x]["last_used"])
            await logger.ainfo(
                f"Maximum sessions reached for server {server_key}, removing oldest session {oldest_session_id}"
            )
            await self._cleanup_session_by_id(server_key, oldest_session_id)

        # Create new session
        session_id = f"{server_key}_{len(sessions)}"
        await logger.ainfo(f"Creating new session {session_id} for server {server_key}")

        if transport_type == "stdio":
            session, task = await self._create_stdio_session(session_id, connection_params)
            actual_transport = "stdio"
        elif transport_type == "streamable_http":
            # Pass the cached transport preference if available
            preferred_transport = self._transport_preference.get(server_key)
            session, task, actual_transport = await self._create_streamable_http_session(
                session_id, connection_params, preferred_transport
            )
            # Cache the transport that worked for future connections
            self._transport_preference[server_key] = actual_transport
        else:
            msg = f"Unknown transport type: {transport_type}"
            raise ValueError(msg)

        # Store session info with the actual transport used
        sessions[session_id] = {
            "session": session,
            "task": task,
            "type": actual_transport,
            "last_used": asyncio.get_event_loop().time(),
        }

        # register mapping & initial ref-count for the new session
        self._context_to_session[context_id] = (server_key, session_id)
        self._session_refcount[(server_key, session_id)] = 1

        return session

    async def _create_stdio_session(self, session_id: str, connection_params):
        """Create a new stdio session as a background task to avoid context issues."""
        import asyncio

        from mcp.client.stdio import stdio_client

        # Create a future to get the session
        session_future: asyncio.Future[ClientSession] = asyncio.Future()

        async def session_task():
            """Background task that keeps the session alive."""
            try:
                async with stdio_client(connection_params) as (read, write):
                    session = ClientSession(read, write)
                    async with session:
                        await session.initialize()
                        # Signal that session is ready
                        session_future.set_result(session)

                        # Keep the session alive until cancelled
                        import anyio

                        event = anyio.Event()
                        try:
                            await event.wait()
                        except asyncio.CancelledError:
                            await logger.ainfo(f"Session {session_id} is shutting down")
            except Exception as e:  # noqa: BLE001
                if not session_future.done():
                    session_future.set_exception(e)

        # Start the background task
        task = asyncio.create_task(session_task())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

        # Wait for session to be ready (use longer timeout for remote connections)
        try:
            session = await asyncio.wait_for(session_future, timeout=30.0)
        except asyncio.TimeoutError as timeout_err:
            # Clean up the failed task
            if not task.done():
                task.cancel()
                import contextlib

                with contextlib.suppress(asyncio.CancelledError):
                    await task
            self._background_tasks.discard(task)
            msg = f"Timeout waiting for STDIO session {session_id} to initialize"
            await logger.aerror(msg)
            raise ValueError(msg) from timeout_err

        return session, task

    async def _create_streamable_http_session(
        self, session_id: str, connection_params, preferred_transport: str | None = None
    ):
        """Create a new Streamable HTTP session with SSE fallback as a background task to avoid context issues.

        Args:
            session_id: Unique identifier for this session
            connection_params: Connection parameters including URL, headers, timeouts, verify_ssl
            preferred_transport: If set to "sse", skip Streamable HTTP and go directly to SSE

        Returns:
            tuple: (session, task, transport_used) where transport_used is "streamable_http" or "sse"
        """
        import asyncio

        from mcp.client.sse import sse_client
        from mcp.client.streamable_http import streamablehttp_client

        # Create a future to get the session
        session_future: asyncio.Future[ClientSession] = asyncio.Future()
        # Track which transport succeeded
        used_transport: list[str] = []

        # Get verify_ssl option from connection params, default to True
        verify_ssl = connection_params.get("verify_ssl", True)

        # Create custom httpx client factory with SSL verification option
        def custom_httpx_factory(
            headers: dict[str, str] | None = None,
            timeout: httpx.Timeout | None = None,
            auth: httpx.Auth | None = None,
        ) -> httpx.AsyncClient:
            return create_mcp_http_client_with_ssl_option(
                headers=headers, timeout=timeout, auth=auth, verify_ssl=verify_ssl
            )

        async def session_task():
            """Background task that keeps the session alive."""
            streamable_error = None

            # Skip Streamable HTTP if we know SSE works for this server
            if preferred_transport != "sse":
                # Try Streamable HTTP first with a quick timeout
                try:
                    await logger.adebug(f"Attempting Streamable HTTP connection for session {session_id}")
                    # Use a shorter timeout for the initial connection attempt (2 seconds)
                    async with streamablehttp_client(
                        url=connection_params["url"],
                        headers=connection_params["headers"],
                        timeout=connection_params["timeout_seconds"],
                        httpx_client_factory=custom_httpx_factory,
                    ) as (read, write, _):
                        session = ClientSession(read, write)
                        async with session:
                            # Initialize with a timeout to fail fast
                            await asyncio.wait_for(session.initialize(), timeout=2.0)
                            used_transport.append("streamable_http")
                            await logger.ainfo(f"Session {session_id} connected via Streamable HTTP")
                            # Signal that session is ready
                            session_future.set_result(session)

                            # Keep the session alive until cancelled
                            import anyio

                            event = anyio.Event()
                            try:
                                await event.wait()
                            except asyncio.CancelledError:
                                await logger.ainfo(f"Session {session_id} (Streamable HTTP) is shutting down")
                except (asyncio.TimeoutError, Exception) as e:  # noqa: BLE001
                    # If Streamable HTTP fails or times out, try SSE as fallback immediately
                    streamable_error = e
                    error_type = "timed out" if isinstance(e, asyncio.TimeoutError) else "failed"
                    await logger.awarning(
                        f"Streamable HTTP {error_type} for session {session_id}: {e}. Falling back to SSE..."
                    )
            else:
                await logger.adebug(f"Skipping Streamable HTTP for session {session_id}, using cached SSE preference")

            # Try SSE if Streamable HTTP failed or if SSE is preferred
            if streamable_error is not None or preferred_transport == "sse":
                try:
                    await logger.adebug(f"Attempting SSE connection for session {session_id}")
                    # Extract SSE read timeout from connection params, default to 30s if not present
                    sse_read_timeout = connection_params.get("sse_read_timeout_seconds", 30)

                    async with sse_client(
                        connection_params["url"],
                        connection_params["headers"],
                        connection_params["timeout_seconds"],
                        sse_read_timeout,
                        httpx_client_factory=custom_httpx_factory,
                    ) as (read, write):
                        session = ClientSession(read, write)
                        async with session:
                            await session.initialize()
                            used_transport.append("sse")
                            fallback_msg = " (fallback)" if streamable_error else " (preferred)"
                            await logger.ainfo(f"Session {session_id} connected via SSE{fallback_msg}")
                            # Signal that session is ready
                            if not session_future.done():
                                session_future.set_result(session)

                            # Keep the session alive until cancelled
                            import anyio

                            event = anyio.Event()
                            try:
                                await event.wait()
                            except asyncio.CancelledError:
                                await logger.ainfo(f"Session {session_id} (SSE) is shutting down")
                except Exception as sse_error:  # noqa: BLE001
                    # Both transports failed (or just SSE if it was preferred)
                    if streamable_error:
                        await logger.aerror(
                            f"Both Streamable HTTP and SSE failed for session {session_id}. "
                            f"Streamable HTTP error: {streamable_error}. SSE error: {sse_error}"
                        )
                        if not session_future.done():
                            session_future.set_exception(
                                ValueError(
                                    f"Failed to connect via Streamable HTTP ({streamable_error}) or SSE ({sse_error})"
                                )
                            )
                    else:
                        await logger.aerror(f"SSE connection failed for session {session_id}: {sse_error}")
                        if not session_future.done():
                            session_future.set_exception(ValueError(f"Failed to connect via SSE: {sse_error}"))

        # Start the background task
        task = asyncio.create_task(session_task())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

        # Wait for session to be ready (use longer timeout for remote connections)
        try:
            session = await asyncio.wait_for(session_future, timeout=30.0)
            # Log which transport was used
            if used_transport:
                transport_used = used_transport[0]
                await logger.ainfo(f"Session {session_id} successfully established using {transport_used}")
                return session, task, transport_used
            # This shouldn't happen, but handle it just in case
            msg = f"Session {session_id} established but transport not recorded"
            raise ValueError(msg)
        except asyncio.TimeoutError as timeout_err:
            # Clean up the failed task
            if not task.done():
                task.cancel()
                import contextlib

                with contextlib.suppress(asyncio.CancelledError):
                    await task
            self._background_tasks.discard(task)
            msg = f"Timeout waiting for Streamable HTTP/SSE session {session_id} to initialize"
            await logger.aerror(msg)
            raise ValueError(msg) from timeout_err

    async def _cleanup_session_by_id(self, server_key: str, session_id: str):
        """Clean up a specific session by server key and session ID."""
        if server_key not in self.sessions_by_server:
            return

        server_data = self.sessions_by_server[server_key]
        # Handle both old and new session structure
        if isinstance(server_data, dict) and "sessions" in server_data:
            sessions = server_data["sessions"]
        else:
            # Handle old structure where sessions were stored directly
            sessions = server_data

        if session_id not in sessions:
            return

        session_info = sessions[session_id]
        try:
            # First try to properly close the session if it exists
            if "session" in session_info:
                session = session_info["session"]

                # Try async close first (aclose method)
                if hasattr(session, "aclose"):
                    try:
                        await session.aclose()
                        await logger.adebug("Successfully closed session %s using aclose()", session_id)
                    except Exception as e:  # noqa: BLE001
                        await logger.adebug("Error closing session %s with aclose(): %s", session_id, e)

                # If no aclose, try regular close method
                elif hasattr(session, "close"):
                    try:
                        # Check if close() is awaitable using inspection
                        if inspect.iscoroutinefunction(session.close):
                            # It's an async method
                            await session.close()
                            await logger.adebug("Successfully closed session %s using async close()", session_id)
                        else:
                            # Try calling it and check if result is awaitable
                            close_result = session.close()
                            if inspect.isawaitable(close_result):
                                await close_result
                                await logger.adebug(
                                    "Successfully closed session %s using awaitable close()", session_id
                                )
                            else:
                                # It's a synchronous close
                                await logger.adebug("Successfully closed session %s using sync close()", session_id)
                    except Exception as e:  # noqa: BLE001
                        await logger.adebug("Error closing session %s with close(): %s", session_id, e)

            # Cancel the background task which will properly close the session
            if "task" in session_info:
                task = session_info["task"]
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        await logger.ainfo(f"Cancelled task for session {session_id}")
        except Exception as e:  # noqa: BLE001
            await logger.awarning(f"Error cleaning up session {session_id}: {e}")
        finally:
            # Remove from sessions dict
            del sessions[session_id]

    async def cleanup_all(self):
        """Clean up all sessions."""
        # Cancel periodic cleanup task
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._cleanup_task

        # Clean up all sessions
        for server_key in list(self.sessions_by_server.keys()):
            server_data = self.sessions_by_server[server_key]
            # Handle both old and new session structure
            if isinstance(server_data, dict) and "sessions" in server_data:
                sessions = server_data["sessions"]
            else:
                # Handle old structure where sessions were stored directly
                sessions = server_data

            for session_id in list(sessions.keys()):
                await self._cleanup_session_by_id(server_key, session_id)

        # Clear the sessions_by_server structure completely
        self.sessions_by_server.clear()

        # Clear compatibility maps
        self._context_to_session.clear()
        self._session_refcount.clear()

        # Clear all background tasks
        for task in list(self._background_tasks):
            if not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

        # Give a bit more time for subprocess transports to clean up
        # This helps prevent the BaseSubprocessTransport.__del__ warnings
        await asyncio.sleep(0.5)

    async def _cleanup_session(self, context_id: str):
        """Backward-compat cleanup by context_id.

        Decrements the ref-count for the session used by *context_id* and only
        tears the session down when the last context that references it goes
        away.
        """
        mapping = self._context_to_session.get(context_id)
        if not mapping:
            await logger.adebug(f"No session mapping found for context_id {context_id}")
            return

        server_key, session_id = mapping
        ref_key = (server_key, session_id)
        remaining = self._session_refcount.get(ref_key, 1) - 1

        if remaining <= 0:
            await self._cleanup_session_by_id(server_key, session_id)
            self._session_refcount.pop(ref_key, None)
        else:
            self._session_refcount[ref_key] = remaining

        # Remove the mapping for this context
        self._context_to_session.pop(context_id, None)


class MCPStdioClient:
    def __init__(self, component_cache=None):
        self.session: ClientSession | None = None
        self._connection_params = None
        self._connected = False
        self._session_context: str | None = None
        self._component_cache = component_cache

    async def _connect_to_server(self, command_str: str, env: dict[str, str] | None = None) -> list[StructuredTool]:
        """Connect to MCP server using stdio transport (SDK style)."""
        from mcp import StdioServerParameters

        command = command_str.split(" ")
        env_data: dict[str, str] = {"DEBUG": "true", "PATH": os.environ["PATH"], **(env or {})}

        if platform.system() == "Windows":
            server_params = StdioServerParameters(
                command="cmd",
                args=[
                    "/c",
                    f"{command[0]} {' '.join(command[1:])} || echo Command failed with exit code %errorlevel% 1>&2",
                ],
                env=env_data,
            )
        else:
            server_params = StdioServerParameters(
                command="bash",
                args=["-c", f"exec {command_str} || echo 'Command failed with exit code $?' >&2"],
                env=env_data,
            )

        # Store connection parameters for later use in run_tool
        self._connection_params = server_params

        # If no session context is set, create a default one
        if not self._session_context:
            # Generate a fallback context based on connection parameters
            import uuid

            param_hash = uuid.uuid4().hex[:8]
            self._session_context = f"default_{param_hash}"

        # Get or create a persistent session
        session = await self._get_or_create_session()
        response = await session.list_tools()
        self._connected = True
        return response.tools

    async def connect_to_server(self, command_str: str, env: dict[str, str] | None = None) -> list[StructuredTool]:
        """Connect to MCP server using stdio transport (SDK style)."""
        return await asyncio.wait_for(
            self._connect_to_server(command_str, env), timeout=get_settings_service().settings.mcp_server_timeout
        )

    def set_session_context(self, context_id: str):
        """Set the session context (e.g., flow_id + user_id + session_id)."""
        self._session_context = context_id

    def _get_session_manager(self) -> MCPSessionManager:
        """Get or create session manager from component cache."""
        if not self._component_cache:
            # Fallback to instance-level session manager if no cache
            if not hasattr(self, "_session_manager"):
                self._session_manager = MCPSessionManager()
            return self._session_manager

        from lfx.services.cache.utils import CacheMiss

        session_manager = self._component_cache.get("mcp_session_manager")
        if isinstance(session_manager, CacheMiss):
            session_manager = MCPSessionManager()
            self._component_cache.set("mcp_session_manager", session_manager)
        return session_manager

    async def _get_or_create_session(self) -> ClientSession:
        """Get or create a persistent session for the current context."""
        if not self._session_context or not self._connection_params:
            msg = "Session context and connection params must be set"
            raise ValueError(msg)

        # Use cached session manager to get/create persistent session
        session_manager = self._get_session_manager()
        return await session_manager.get_session(self._session_context, self._connection_params, "stdio")

    async def run_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Run a tool with the given arguments using context-specific session.

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

        # If no session context is set, create a default one
        if not self._session_context:
            # Generate a fallback context based on connection parameters
            import uuid

            param_hash = uuid.uuid4().hex[:8]
            self._session_context = f"default_{param_hash}"

        max_retries = 2
        last_error_type = None

        for attempt in range(max_retries):
            try:
                await logger.adebug(f"Attempting to run tool '{tool_name}' (attempt {attempt + 1}/{max_retries})")
                # Get or create persistent session
                session = await self._get_or_create_session()

                result = await asyncio.wait_for(
                    session.call_tool(tool_name, arguments=arguments),
                    timeout=30.0,  # 30 second timeout
                )
            except Exception as e:
                current_error_type = type(e).__name__
                await logger.awarning(f"Tool '{tool_name}' failed on attempt {attempt + 1}: {current_error_type} - {e}")

                # Import specific MCP error types for detection
                try:
                    is_closed_resource_error = isinstance(e, ClosedResourceError)
                    is_mcp_connection_error = isinstance(e, McpError) and "Connection closed" in str(e)
                except ImportError:
                    is_closed_resource_error = "ClosedResourceError" in str(type(e))
                    is_mcp_connection_error = "Connection closed" in str(e)

                # Detect timeout errors
                is_timeout_error = isinstance(e, asyncio.TimeoutError | TimeoutError)

                # If we're getting the same error type repeatedly, don't retry
                if last_error_type == current_error_type and attempt > 0:
                    await logger.aerror(f"Repeated {current_error_type} error for tool '{tool_name}', not retrying")
                    break

                last_error_type = current_error_type

                # If it's a connection error (ClosedResourceError or MCP connection closed) and we have retries left
                if (is_closed_resource_error or is_mcp_connection_error) and attempt < max_retries - 1:
                    await logger.awarning(
                        f"MCP session connection issue for tool '{tool_name}', retrying with fresh session..."
                    )
                    # Clean up the dead session
                    if self._session_context:
                        session_manager = self._get_session_manager()
                        await session_manager._cleanup_session(self._session_context)
                    # Add a small delay before retry
                    await asyncio.sleep(0.5)
                    continue

                # If it's a timeout error and we have retries left, try once more
                if is_timeout_error and attempt < max_retries - 1:
                    await logger.awarning(f"Tool '{tool_name}' timed out, retrying...")
                    # Don't clean up session for timeouts, might just be a slow response
                    await asyncio.sleep(1.0)
                    continue

                # For other errors or no retries left, handle as before
                if (
                    isinstance(e, ConnectionError | TimeoutError | OSError | ValueError)
                    or is_closed_resource_error
                    or is_mcp_connection_error
                    or is_timeout_error
                ):
                    msg = f"Failed to run tool '{tool_name}' after {attempt + 1} attempts: {e}"
                    await logger.aerror(msg)
                    # Clean up failed session from cache
                    if self._session_context and self._component_cache:
                        cache_key = f"mcp_session_stdio_{self._session_context}"
                        self._component_cache.delete(cache_key)
                    self._connected = False
                    raise ValueError(msg) from e
                # Re-raise unexpected errors
                raise
            else:
                await logger.adebug(f"Tool '{tool_name}' completed successfully")
                return result

        # This should never be reached due to the exception handling above
        msg = f"Failed to run tool '{tool_name}': Maximum retries exceeded with repeated {last_error_type} errors"
        await logger.aerror(msg)
        raise ValueError(msg)

    async def disconnect(self):
        """Properly close the connection and clean up resources."""
        # For stdio transport, there is no remote session to terminate explicitly
        # The session cleanup happens when the background task is cancelled

        # Clean up local session using the session manager
        if self._session_context:
            session_manager = self._get_session_manager()
            await session_manager._cleanup_session(self._session_context)

        # Reset local state
        self.session = None
        self._connection_params = None
        self._connected = False
        self._session_context = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()


class MCPStreamableHttpClient:
    def __init__(self, component_cache=None):
        self.session: ClientSession | None = None
        self._connection_params = None
        self._connected = False
        self._session_context: str | None = None
        self._component_cache = component_cache

    def _get_session_manager(self) -> MCPSessionManager:
        """Get or create session manager from component cache."""
        if not self._component_cache:
            # Fallback to instance-level session manager if no cache
            if not hasattr(self, "_session_manager"):
                self._session_manager = MCPSessionManager()
            return self._session_manager

        from lfx.services.cache.utils import CacheMiss

        session_manager = self._component_cache.get("mcp_session_manager")
        if isinstance(session_manager, CacheMiss):
            session_manager = MCPSessionManager()
            self._component_cache.set("mcp_session_manager", session_manager)
        return session_manager

    async def validate_url(self, url: str | None) -> tuple[bool, str]:
        """Validate the Streamable HTTP URL before attempting connection."""
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return False, "Invalid URL format. Must include scheme (http/https) and host."
        except (ValueError, OSError) as e:
            return False, f"URL validation error: {e!s}"
        return True, ""

    async def _connect_to_server(
        self,
        url: str | None,
        headers: dict[str, str] | None = None,
        timeout_seconds: int = 30,
        sse_read_timeout_seconds: int = 30,
        *,
        verify_ssl: bool = True,
    ) -> list[StructuredTool]:
        """Connect to MCP server using Streamable HTTP transport with SSE fallback (SDK style)."""
        # Validate and sanitize headers early
        validated_headers = _process_headers(headers)

        if url is None:
            msg = "URL is required for StreamableHTTP or SSE mode"
            raise ValueError(msg)

        # Only validate URL if we don't have a cached session
        # This avoids expensive HTTP validation calls when reusing sessions
        if not self._connected or not self._connection_params:
            is_valid, error_msg = await self.validate_url(url)
            if not is_valid:
                msg = f"Invalid Streamable HTTP or SSE URL ({url}): {error_msg}"
                raise ValueError(msg)
            # Store connection parameters for later use in run_tool
            # Include SSE read timeout for fallback and SSL verification option
            self._connection_params = {
                "url": url,
                "headers": validated_headers,
                "timeout_seconds": timeout_seconds,
                "sse_read_timeout_seconds": sse_read_timeout_seconds,
                "verify_ssl": verify_ssl,
            }
        elif headers:
            self._connection_params["headers"] = validated_headers

        # If no session context is set, create a default one
        if not self._session_context:
            # Generate a fallback context based on connection parameters
            import uuid

            param_hash = uuid.uuid4().hex[:8]
            self._session_context = f"default_http_{param_hash}"

        # Get or create a persistent session (will try Streamable HTTP, then SSE fallback)
        session = await self._get_or_create_session()
        response = await session.list_tools()
        self._connected = True
        return response.tools

    async def connect_to_server(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        sse_read_timeout_seconds: int = 30,
        *,
        verify_ssl: bool = True,
    ) -> list[StructuredTool]:
        """Connect to MCP server using Streamable HTTP with SSE fallback transport (SDK style)."""
        return await asyncio.wait_for(
            self._connect_to_server(
                url, headers, sse_read_timeout_seconds=sse_read_timeout_seconds, verify_ssl=verify_ssl
            ),
            timeout=get_settings_service().settings.mcp_server_timeout,
        )

    def set_session_context(self, context_id: str):
        """Set the session context (e.g., flow_id + user_id + session_id)."""
        self._session_context = context_id

    async def _get_or_create_session(self) -> ClientSession:
        """Get or create a persistent session for the current context."""
        if not self._session_context or not self._connection_params:
            msg = "Session context and params must be set"
            raise ValueError(msg)

        # Use cached session manager to get/create persistent session
        session_manager = self._get_session_manager()
        # Cache session so we can access server-assigned session_id later for DELETE
        self.session = await session_manager.get_session(
            self._session_context, self._connection_params, "streamable_http"
        )
        return self.session

    async def _terminate_remote_session(self) -> None:
        """Attempt to explicitly terminate the remote MCP session via HTTP DELETE (best-effort)."""
        # Only relevant for Streamable HTTP or SSE transport
        if not self._connection_params or "url" not in self._connection_params:
            return

        url: str = self._connection_params["url"]

        # Retrieve session id from the underlying SDK if exposed
        session_id = None
        if getattr(self, "session", None) is not None:
            # Common attributes in MCP python SDK: `session_id` or `id`
            session_id = getattr(self.session, "session_id", None) or getattr(self.session, "id", None)

        headers: dict[str, str] = dict(self._connection_params.get("headers", {}))
        if session_id:
            headers["Mcp-Session-Id"] = str(session_id)

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.delete(url, headers=headers)
        except Exception as e:  # noqa: BLE001
            # DELETE is advisory—log and continue
            logger.debug(f"Unable to send session DELETE to '{url}': {e}")

    async def run_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Run a tool with the given arguments using context-specific session.

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

        # If no session context is set, create a default one
        if not self._session_context:
            # Generate a fallback context based on connection parameters
            import uuid

            param_hash = uuid.uuid4().hex[:8]
            self._session_context = f"default_http_{param_hash}"

        max_retries = 2
        last_error_type = None

        for attempt in range(max_retries):
            try:
                await logger.adebug(f"Attempting to run tool '{tool_name}' (attempt {attempt + 1}/{max_retries})")
                # Get or create persistent session
                session = await self._get_or_create_session()

                result = await asyncio.wait_for(
                    session.call_tool(tool_name, arguments=arguments),
                    timeout=30.0,  # 30 second timeout
                )
            except Exception as e:
                current_error_type = type(e).__name__
                await logger.awarning(f"Tool '{tool_name}' failed on attempt {attempt + 1}: {current_error_type} - {e}")

                # Import specific MCP error types for detection
                try:
                    from anyio import ClosedResourceError
                    from mcp.shared.exceptions import McpError

                    is_closed_resource_error = isinstance(e, ClosedResourceError)
                    is_mcp_connection_error = isinstance(e, McpError) and "Connection closed" in str(e)
                except ImportError:
                    is_closed_resource_error = "ClosedResourceError" in str(type(e))
                    is_mcp_connection_error = "Connection closed" in str(e)

                # Detect timeout errors
                is_timeout_error = isinstance(e, asyncio.TimeoutError | TimeoutError)

                # If we're getting the same error type repeatedly, don't retry
                if last_error_type == current_error_type and attempt > 0:
                    await logger.aerror(f"Repeated {current_error_type} error for tool '{tool_name}', not retrying")
                    break

                last_error_type = current_error_type

                # If it's a connection error (ClosedResourceError or MCP connection closed) and we have retries left
                if (is_closed_resource_error or is_mcp_connection_error) and attempt < max_retries - 1:
                    await logger.awarning(
                        f"MCP session connection issue for tool '{tool_name}', retrying with fresh session..."
                    )
                    # Clean up the dead session
                    if self._session_context:
                        session_manager = self._get_session_manager()
                        await session_manager._cleanup_session(self._session_context)
                    # Add a small delay before retry
                    await asyncio.sleep(0.5)
                    continue

                # If it's a timeout error and we have retries left, try once more
                if is_timeout_error and attempt < max_retries - 1:
                    await logger.awarning(f"Tool '{tool_name}' timed out, retrying...")
                    # Don't clean up session for timeouts, might just be a slow response
                    await asyncio.sleep(1.0)
                    continue

                # For other errors or no retries left, handle as before
                if (
                    isinstance(e, ConnectionError | TimeoutError | OSError | ValueError)
                    or is_closed_resource_error
                    or is_mcp_connection_error
                    or is_timeout_error
                ):
                    msg = f"Failed to run tool '{tool_name}' after {attempt + 1} attempts: {e}"
                    await logger.aerror(msg)
                    # Clean up failed session from cache
                    if self._session_context and self._component_cache:
                        cache_key = f"mcp_session_http_{self._session_context}"
                        self._component_cache.delete(cache_key)
                    self._connected = False
                    raise ValueError(msg) from e
                # Re-raise unexpected errors
                raise
            else:
                await logger.adebug(f"Tool '{tool_name}' completed successfully")
                return result

        # This should never be reached due to the exception handling above
        msg = f"Failed to run tool '{tool_name}': Maximum retries exceeded with repeated {last_error_type} errors"
        await logger.aerror(msg)
        raise ValueError(msg)

    async def disconnect(self):
        """Properly close the connection and clean up resources."""
        # Attempt best-effort remote session termination first
        await self._terminate_remote_session()

        # Clean up local session using the session manager
        if self._session_context:
            session_manager = self._get_session_manager()
            await session_manager._cleanup_session(self._session_context)

        # Reset local state
        self.session = None
        self._connection_params = None
        self._connected = False
        self._session_context = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()


# Backward compatibility: MCPSseClient is now an alias for MCPStreamableHttpClient
# The new client supports both Streamable HTTP and SSE with automatic fallback
MCPSseClient = MCPStreamableHttpClient


async def update_tools(
    server_name: str,
    server_config: dict,
    mcp_stdio_client: MCPStdioClient | None = None,
    mcp_streamable_http_client: MCPStreamableHttpClient | None = None,
    mcp_sse_client: MCPStreamableHttpClient | None = None,  # Backward compatibility
) -> tuple[str, list[StructuredTool], dict[str, StructuredTool]]:
    """Fetch server config and update available tools."""
    if server_config is None:
        server_config = {}
    if not server_name:
        return "", [], {}
    if mcp_stdio_client is None:
        mcp_stdio_client = MCPStdioClient()

    # Backward compatibility: accept mcp_sse_client parameter
    if mcp_streamable_http_client is None:
        mcp_streamable_http_client = mcp_sse_client if mcp_sse_client is not None else MCPStreamableHttpClient()

    # Fetch server config from backend
    # Determine mode from config, defaulting to Streamable_HTTP if URL present
    mode = server_config.get("mode", "")
    if not mode:
        mode = "Stdio" if "command" in server_config else "Streamable_HTTP" if "url" in server_config else ""

    command = server_config.get("command", "")
    url = server_config.get("url", "")
    tools = []
    headers = _process_headers(server_config.get("headers", {}))

    try:
        await _validate_connection_params(mode, command, url)
    except ValueError as e:
        logger.error(f"Invalid MCP server configuration for '{server_name}': {e}")
        raise

    # Determine connection type and parameters
    client: MCPStdioClient | MCPStreamableHttpClient | None = None
    if mode == "Stdio":
        # Stdio connection
        args = server_config.get("args", [])
        env = server_config.get("env", {})
        full_command = " ".join([command, *args])
        tools = await mcp_stdio_client.connect_to_server(full_command, env)
        client = mcp_stdio_client
    elif mode in ["Streamable_HTTP", "SSE"]:
        # Streamable HTTP connection with SSE fallback
        verify_ssl = server_config.get("verify_ssl", True)
        tools = await mcp_streamable_http_client.connect_to_server(url, headers=headers, verify_ssl=verify_ssl)
        client = mcp_streamable_http_client
    else:
        logger.error(f"Invalid MCP server mode for '{server_name}': {mode}")
        return "", [], {}

    if not tools or not client or not client._connected:
        logger.warning(f"No tools available from MCP server '{server_name}' or connection failed")
        return "", [], {}

    tool_list = []
    tool_cache: dict[str, StructuredTool] = {}
    for tool in tools:
        if not tool or not hasattr(tool, "name"):
            continue
        try:
            args_schema = create_input_schema_from_json_schema(tool.inputSchema)
            if not args_schema:
                logger.warning(f"Could not create schema for tool '{tool.name}' from server '{server_name}'")
                continue

            # Create a custom StructuredTool that bypasses schema validation
            class MCPStructuredTool(StructuredTool):
                def run(self, tool_input: str | dict, config=None, **kwargs):
                    """Override the main run method to handle parameter conversion before validation."""
                    # Parse tool_input if it's a string
                    if isinstance(tool_input, str):
                        try:
                            parsed_input = json.loads(tool_input)
                        except json.JSONDecodeError:
                            parsed_input = {"input": tool_input}
                    else:
                        parsed_input = tool_input or {}

                    # Convert camelCase parameters to snake_case
                    converted_input = self._convert_parameters(parsed_input)

                    # Call the parent run method with converted parameters
                    return super().run(converted_input, config=config, **kwargs)

                async def arun(self, tool_input: str | dict, config=None, **kwargs):
                    """Override the main arun method to handle parameter conversion before validation."""
                    # Parse tool_input if it's a string
                    if isinstance(tool_input, str):
                        try:
                            parsed_input = json.loads(tool_input)
                        except json.JSONDecodeError:
                            parsed_input = {"input": tool_input}
                    else:
                        parsed_input = tool_input or {}

                    # Convert camelCase parameters to snake_case
                    converted_input = self._convert_parameters(parsed_input)

                    # Call the parent arun method with converted parameters
                    return await super().arun(converted_input, config=config, **kwargs)

                def _convert_parameters(self, input_dict):
                    if not input_dict or not isinstance(input_dict, dict):
                        return input_dict

                    converted_dict = {}
                    original_fields = set(self.args_schema.model_fields.keys())

                    for key, value in input_dict.items():
                        if key in original_fields:
                            # Field exists as-is
                            converted_dict[key] = value
                        else:
                            # Try to convert camelCase to snake_case
                            snake_key = _camel_to_snake(key)
                            if snake_key in original_fields:
                                converted_dict[snake_key] = value
                            else:
                                # Keep original key
                                converted_dict[key] = value

                    return converted_dict

            tool_obj = MCPStructuredTool(
                name=tool.name,
                description=tool.description or "",
                args_schema=args_schema,
                func=create_tool_func(tool.name, args_schema, client),
                coroutine=create_tool_coroutine(tool.name, args_schema, client),
                tags=[tool.name],
                metadata={"server_name": server_name},
            )

            tool_list.append(tool_obj)
            tool_cache[tool.name] = tool_obj
        except (ConnectionError, TimeoutError, OSError, ValueError) as e:
            logger.error(f"Failed to create tool '{tool.name}' from server '{server_name}': {e}")
            msg = f"Failed to create tool '{tool.name}' from server '{server_name}': {e}"
            raise ValueError(msg) from e

    logger.info(f"Successfully loaded {len(tool_list)} tools from MCP server '{server_name}'")
    return mode, tool_list, tool_cache

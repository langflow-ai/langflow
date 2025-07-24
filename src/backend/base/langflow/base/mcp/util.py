import asyncio
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
from loguru import logger
from mcp import ClientSession
from mcp.shared.exceptions import McpError
from pydantic import BaseModel, Field, create_model
from sqlmodel import select

from langflow.services.database.models.flow.model import Flow
from langflow.services.deps import get_settings_service

HTTP_ERROR_STATUS_CODE = httpx_codes.BAD_REQUEST  # HTTP status code for client errors
NULLABLE_TYPE_LENGTH = 2  # Number of types in a nullable union (the type itself + null)

# HTTP status codes used in validation
HTTP_NOT_FOUND = 404
HTTP_BAD_REQUEST = 400
HTTP_INTERNAL_SERVER_ERROR = 500

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
        # Validate input and fill defaults for missing optional fields
        try:
            validated = arg_schema.model_validate(provided_args)
        except Exception as e:
            msg = f"Invalid input: {e}"
            raise ValueError(msg) from e

        try:
            return await client.run_tool(tool_name, arguments=validated.model_dump())
        except Exception as e:
            logger.error(f"Tool '{tool_name}' execution failed: {e}")
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
        try:
            validated = arg_schema.model_validate(provided_args)
        except Exception as e:
            msg = f"Invalid input: {e}"
            raise ValueError(msg) from e

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


async def get_flow_snake_case(flow_name: str, user_id: str, session, is_action: bool | None = None) -> Flow | None:
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


def create_input_schema_from_json_schema(schema: dict[str, Any]) -> type[BaseModel]:
    """Dynamically build a Pydantic model from a JSON schema (with $defs).

    Non-required fields become Optional[...] with default=None.
    """
    if schema.get("type") != "object":
        msg = "Root schema must be type 'object'"
        raise ValueError(msg)

    defs: dict[str, dict[str, Any]] = schema.get("$defs", {})
    model_cache: dict[str, type[BaseModel]] = {}

    def resolve_ref(s: dict[str, Any] | None) -> dict[str, Any]:
        """Follow a $ref chain until you land on a real subschema."""
        if s is None:
            return {}
        while "$ref" in s:
            ref_name = s["$ref"].split("/")[-1]
            s = defs.get(ref_name)
            if s is None:
                logger.warning(f"Parsing input schema: Definition '{ref_name}' not found")
                return {"type": "string"}
        return s

    def parse_type(s: dict[str, Any] | None) -> Any:
        """Map a JSON Schema subschema to a Python type (possibly nested)."""
        if s is None:
            return None
        s = resolve_ref(s)

        if "anyOf" in s:
            # Handle common pattern for nullable types (anyOf with string and null)
            subtypes = [sub.get("type") for sub in s["anyOf"] if isinstance(sub, dict) and "type" in sub]

            # Check if this is a simple nullable type (e.g., str | None)
            if len(subtypes) == NULLABLE_TYPE_LENGTH and "null" in subtypes:
                # Get the non-null type
                non_null_type = next(t for t in subtypes if t != "null")
                # Map it to Python type
                if isinstance(non_null_type, str):
                    return {
                        "string": str,
                        "integer": int,
                        "number": float,
                        "boolean": bool,
                        "object": dict,
                        "array": list,
                    }.get(non_null_type, Any)
                return Any

            # For other anyOf cases, use the first non-null type
            subtypes = [parse_type(sub) for sub in s["anyOf"]]
            non_null_types = [t for t in subtypes if t is not None and t is not type(None)]
            if non_null_types:
                return non_null_types[0]
            return str

        t = s.get("type", "any")  # Use string "any" as default instead of Any type
        if t == "array":
            item_schema = s.get("items", {})
            schema_type: Any = parse_type(item_schema)
            return list[schema_type]

        if t == "object":
            # inline object not in $defs ⇒ anonymous nested model
            return _build_model(f"AnonModel{len(model_cache)}", s)

        # primitive fallback
        return {
            "string": str,
            "integer": int,
            "number": float,
            "boolean": bool,
            "object": dict,
            "array": list,
        }.get(t, Any)

    def _build_model(name: str, subschema: dict[str, Any]) -> type[BaseModel]:
        """Create (or fetch) a BaseModel subclass for the given object schema."""
        # If this came via a named $ref, use that name
        if "$ref" in subschema:
            refname = subschema["$ref"].split("/")[-1]
            if refname in model_cache:
                return model_cache[refname]
            target = defs.get(refname)
            if not target:
                msg = f"Definition '{refname}' not found"
                raise ValueError(msg)
            cls = _build_model(refname, target)
            model_cache[refname] = cls
            return cls

        # Named anonymous or inline: avoid clashes by name
        if name in model_cache:
            return model_cache[name]

        props = subschema.get("properties", {})
        reqs = set(subschema.get("required", []))
        fields: dict[str, Any] = {}

        for prop_name, prop_schema in props.items():
            py_type = parse_type(prop_schema)
            is_required = prop_name in reqs
            if not is_required:
                py_type = py_type | None
                default = prop_schema.get("default", None)
            else:
                default = ...  # required by Pydantic

            fields[prop_name] = (py_type, Field(default, description=prop_schema.get("description")))

        model_cls = create_model(name, **fields)
        model_cache[name] = model_cls
        return model_cls

    # build the top - level "InputSchema" from the root properties
    top_props = schema.get("properties", {})
    top_reqs = set(schema.get("required", []))
    top_fields: dict[str, Any] = {}

    for fname, fdef in top_props.items():
        py_type = parse_type(fdef)
        if fname not in top_reqs:
            py_type = py_type | None
            default = fdef.get("default", None)
        else:
            default = ...
        top_fields[fname] = (py_type, Field(default, description=fdef.get("description")))

    return create_model("InputSchema", **top_fields)


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
    if mode not in ["Stdio", "SSE"]:
        msg = f"Invalid mode: {mode}. Must be either 'Stdio' or 'SSE'"
        raise ValueError(msg)

    if mode == "Stdio" and not command:
        msg = "Command is required for Stdio mode"
        raise ValueError(msg)
    if mode == "Stdio" and command:
        _validate_node_installation(command)
    if mode == "SSE" and not url:
        msg = "URL is required for SSE mode"
        raise ValueError(msg)


class MCPSessionManager:
    """Manages persistent MCP sessions with proper context manager lifecycle."""

    def __init__(self):
        self.sessions = {}  # context_id -> session_info
        self._background_tasks = set()  # Keep references to background tasks
        self._last_server_by_session = {}  # context_id -> server_name for tracking switches

    async def _validate_session_connectivity(self, session) -> bool:
        """Validate that the session is actually usable by testing a simple operation."""
        try:
            # Try to list tools as a connectivity test (this is a lightweight operation)
            # Use a shorter timeout for the connectivity test to fail fast
            response = await asyncio.wait_for(session.list_tools(), timeout=3.0)
        except (asyncio.TimeoutError, ConnectionError, OSError, ValueError) as e:
            logger.debug(f"Session connectivity test failed (standard error): {e}")
            return False
        except Exception as e:
            # Handle MCP-specific errors that might not be in the standard list
            error_str = str(e)
            if (
                "ClosedResourceError" in str(type(e))
                or "Connection closed" in error_str
                or "Connection lost" in error_str
                or "Transport closed" in error_str
                or "Stream closed" in error_str
            ):
                logger.debug(f"Session connectivity test failed (MCP connection error): {e}")
                return False
            # Re-raise unexpected errors
            logger.warning(f"Unexpected error in connectivity test: {e}")
            raise
        else:
            # Validate that we got a meaningful response
            if response is None:
                logger.debug("Session connectivity test failed: received None response")
                return False
            try:
                # Check if we can access the tools list (even if empty)
                tools = getattr(response, "tools", None)
                if tools is None:
                    logger.debug("Session connectivity test failed: no tools attribute in response")
                    return False
            except (AttributeError, TypeError) as e:
                logger.debug(f"Session connectivity test failed while validating response: {e}")
                return False
            else:
                logger.debug(f"Session connectivity test passed: found {len(tools)} tools")
                return True

    async def get_session(self, context_id: str, connection_params, transport_type: str):
        """Get or create a persistent session."""
        # Extract server identifier from connection params for tracking
        server_identifier = None
        if transport_type == "stdio" and hasattr(connection_params, "command"):
            server_identifier = f"stdio_{connection_params.command}"
        elif transport_type == "sse" and isinstance(connection_params, dict) and "url" in connection_params:
            server_identifier = f"sse_{connection_params['url']}"

        # Check if we're switching servers for this context
        server_switched = False
        if context_id in self._last_server_by_session:
            last_server = self._last_server_by_session[context_id]
            if last_server != server_identifier:
                server_switched = True
                logger.info(f"Detected server switch for context {context_id}: {last_server} -> {server_identifier}")

        # Update server tracking
        if server_identifier:
            self._last_server_by_session[context_id] = server_identifier

        if context_id in self.sessions:
            session_info = self.sessions[context_id]
            # Check if session and background task are still alive
            try:
                session = session_info["session"]
                task = session_info["task"]

                # Break down the health check to understand why cleanup is triggered
                task_not_done = not task.done()

                # Additional check for stream health
                stream_is_healthy = True
                try:
                    # Check if the session's write stream is still open
                    if hasattr(session, "_write_stream"):
                        write_stream = session._write_stream

                        # Check for explicit closed state
                        if hasattr(write_stream, "_closed") and write_stream._closed:
                            stream_is_healthy = False
                        # Check anyio stream state for send channels
                        elif hasattr(write_stream, "_state") and hasattr(write_stream._state, "open_send_channels"):
                            # Stream is healthy if there are open send channels
                            stream_is_healthy = write_stream._state.open_send_channels > 0
                        # Check for other stream closed indicators
                        elif hasattr(write_stream, "is_closing") and callable(write_stream.is_closing):
                            stream_is_healthy = not write_stream.is_closing()
                        # If we can't determine state definitively, try a simple write test
                        else:
                            # For streams we can't easily check, assume healthy unless proven otherwise
                            # The actual tool call will reveal if the stream is truly dead
                            stream_is_healthy = True

                except (AttributeError, TypeError) as e:
                    # If we can't check stream health due to missing attributes,
                    # assume it's healthy and let the tool call fail if it's not
                    logger.debug(f"Could not check stream health for context_id {context_id}: {e}")
                    stream_is_healthy = True

                logger.debug(f"Session health check for context_id {context_id}:")
                logger.debug(f"  - task_not_done: {task_not_done}")
                logger.debug(f"  - stream_is_healthy: {stream_is_healthy}")

                # For MCP ClientSession, we need both task and stream to be healthy
                session_is_healthy = task_not_done and stream_is_healthy

                logger.debug(f"  - session_is_healthy: {session_is_healthy}")

                # If we switched servers, always recreate the session to avoid cross-server contamination
                if server_switched:
                    logger.info(f"Server switch detected for context_id {context_id}, forcing session recreation")
                    session_is_healthy = False

                # Always run connectivity test for sessions to ensure they're truly responsive
                # This is especially important when switching between servers
                elif session_is_healthy:
                    logger.debug(f"Running connectivity test for context_id {context_id}")
                    connectivity_ok = await self._validate_session_connectivity(session)
                    logger.debug(f"  - connectivity_ok: {connectivity_ok}")
                    if not connectivity_ok:
                        session_is_healthy = False
                        logger.info(
                            f"Session for context_id {context_id} failed connectivity test, marking as unhealthy"
                        )

                if session_is_healthy:
                    logger.debug(f"Session for context_id {context_id} is healthy and responsive, reusing")
                    return session

                if not task_not_done:
                    msg = f"Session for context_id {context_id} failed health check: background task is done"
                    logger.info(msg)
                elif not stream_is_healthy:
                    msg = f"Session for context_id {context_id} failed health check: stream is closed"
                    logger.info(msg)

            except Exception as e:  # noqa: BLE001
                msg = f"Session for context_id {context_id} is dead due to exception: {e}"
                logger.info(msg)
            # Session is dead, clean it up
            await self._cleanup_session(context_id)

        # Create new session
        if transport_type == "stdio":
            return await self._create_stdio_session(context_id, connection_params)
        if transport_type == "sse":
            return await self._create_sse_session(context_id, connection_params)
        msg = f"Unknown transport type: {transport_type}"
        raise ValueError(msg)

    async def _create_stdio_session(self, context_id: str, connection_params):
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
                            # Session is being shut down
                            msg = "Message is shutting down"
                            logger.info(msg)
            except Exception as e:  # noqa: BLE001
                if not session_future.done():
                    session_future.set_exception(e)

        # Start the background task
        task = asyncio.create_task(session_task())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

        # Wait for session to be ready
        try:
            session = await asyncio.wait_for(session_future, timeout=10.0)  # 10 second timeout for session creation
        except asyncio.TimeoutError as timeout_err:
            # Clean up the failed task
            if not task.done():
                task.cancel()
                import contextlib

                with contextlib.suppress(asyncio.CancelledError):
                    await task
            self._background_tasks.discard(task)
            msg = f"Timeout waiting for STDIO session to initialize for context {context_id}"
            logger.error(msg)
            raise ValueError(msg) from timeout_err
        else:
            # Store session info
            self.sessions[context_id] = {"session": session, "task": task, "type": "stdio"}
            return session

    async def _create_sse_session(self, context_id: str, connection_params):
        """Create a new SSE session as a background task to avoid context issues."""
        import asyncio

        from mcp.client.sse import sse_client

        # Create a future to get the session
        session_future: asyncio.Future[ClientSession] = asyncio.Future()

        async def session_task():
            """Background task that keeps the session alive."""
            try:
                async with sse_client(
                    connection_params["url"],
                    connection_params["headers"],
                    connection_params["timeout_seconds"],
                    connection_params["sse_read_timeout_seconds"],
                ) as (read, write):
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
                            # Session is being shut down
                            msg = "Message is shutting down"
                            logger.info(msg)
            except Exception as e:  # noqa: BLE001
                if not session_future.done():
                    session_future.set_exception(e)

        # Start the background task
        task = asyncio.create_task(session_task())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

        # Wait for session to be ready
        try:
            session = await asyncio.wait_for(session_future, timeout=10.0)  # 10 second timeout for session creation
        except asyncio.TimeoutError as timeout_err:
            # Clean up the failed task
            if not task.done():
                task.cancel()
                import contextlib

                with contextlib.suppress(asyncio.CancelledError):
                    await task
            self._background_tasks.discard(task)
            msg = f"Timeout waiting for SSE session to initialize for context {context_id}"
            logger.error(msg)
            raise ValueError(msg) from timeout_err
        else:
            # Store session info
            self.sessions[context_id] = {"session": session, "task": task, "type": "sse"}
            return session

    async def _cleanup_session(self, context_id: str):
        """Clean up a session by cancelling its background task."""
        if context_id not in self.sessions:
            return

        session_info = self.sessions[context_id]
        try:
            # Cancel the background task which will properly close the session
            if "task" in session_info:
                task = session_info["task"]
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        logger.info(f"Issue cancelling task for context_id {context_id}")
        except Exception as e:  # noqa: BLE001
            logger.info(f"issue cleaning up mcp session: {e}")
        finally:
            del self.sessions[context_id]
            # Also clean up server tracking
            if context_id in self._last_server_by_session:
                del self._last_server_by_session[context_id]

    async def cleanup_all(self):
        """Clean up all sessions."""
        for context_id in list(self.sessions.keys()):
            await self._cleanup_session(context_id)


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

        from langflow.services.cache.utils import CacheMiss

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
                logger.debug(f"Attempting to run tool '{tool_name}' (attempt {attempt + 1}/{max_retries})")
                # Get or create persistent session
                session = await self._get_or_create_session()

                result = await asyncio.wait_for(
                    session.call_tool(tool_name, arguments=arguments),
                    timeout=30.0,  # 30 second timeout
                )
            except Exception as e:
                current_error_type = type(e).__name__
                logger.warning(f"Tool '{tool_name}' failed on attempt {attempt + 1}: {current_error_type} - {e}")

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
                    logger.error(f"Repeated {current_error_type} error for tool '{tool_name}', not retrying")
                    break

                last_error_type = current_error_type

                # If it's a connection error (ClosedResourceError or MCP connection closed) and we have retries left
                if (is_closed_resource_error or is_mcp_connection_error) and attempt < max_retries - 1:
                    logger.warning(
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
                    logger.warning(f"Tool '{tool_name}' timed out, retrying...")
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
                    logger.error(msg)
                    # Clean up failed session from cache
                    if self._session_context and self._component_cache:
                        cache_key = f"mcp_session_stdio_{self._session_context}"
                        self._component_cache.delete(cache_key)
                    self._connected = False
                    raise ValueError(msg) from e
                # Re-raise unexpected errors
                raise
            else:
                logger.debug(f"Tool '{tool_name}' completed successfully")
                return result

        # This should never be reached due to the exception handling above
        msg = f"Failed to run tool '{tool_name}': Maximum retries exceeded with repeated {last_error_type} errors"
        logger.error(msg)
        raise ValueError(msg)

    async def disconnect(self):
        """Properly close the connection and clean up resources."""
        # Clean up session using session manager
        if self._session_context:
            session_manager = self._get_session_manager()
            await session_manager._cleanup_session(self._session_context)

        self.session = None
        self._connection_params = None
        self._connected = False
        self._session_context = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()


class MCPSseClient:
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

        from langflow.services.cache.utils import CacheMiss

        session_manager = self._component_cache.get("mcp_session_manager")
        if isinstance(session_manager, CacheMiss):
            session_manager = MCPSessionManager()
            self._component_cache.set("mcp_session_manager", session_manager)
        return session_manager

    async def validate_url(self, url: str | None, headers: dict[str, str] | None = None ) -> tuple[bool, str]:
        """Validate the SSE URL before attempting connection."""
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return False, "Invalid URL format. Must include scheme (http/https) and host."

            async with httpx.AsyncClient() as client:
                try:
                    # For SSE endpoints, try a GET request with short timeout
                    # Many SSE servers don't support HEAD requests and return 404
                    response = await client.get(url, timeout=2.0, headers={"Accept": "text/event-stream", **headers})

                    # For SSE, we expect the server to either:
                    # 1. Start streaming (200)
                    # 2. Return 404 if HEAD/GET without proper SSE handshake is not supported
                    # 3. Return other status codes that we should handle gracefully

                    # Don't fail on 404 since many SSE endpoints return this for non-SSE requests
                    if response.status_code == HTTP_NOT_FOUND:
                        # This is likely an SSE endpoint that doesn't support regular GET
                        # Let the actual SSE connection attempt handle this
                        return True, ""

                    # Fail on client errors except 404, but allow server errors and redirects
                    if (
                        HTTP_BAD_REQUEST <= response.status_code < HTTP_INTERNAL_SERVER_ERROR
                        and response.status_code != HTTP_NOT_FOUND
                    ):
                        return False, f"Server returned client error status: {response.status_code}"

                except httpx.TimeoutException:
                    # Timeout on a short request might indicate the server is trying to stream
                    # This is actually expected behavior for SSE endpoints
                    return True, ""
                except httpx.NetworkError:
                    return False, "Network error. Could not reach the server."
                else:
                    return True, ""

        except (httpx.HTTPError, ValueError, OSError) as e:
            return False, f"URL validation error: {e!s}"

    async def pre_check_redirect(self, url: str | None, headers: dict[str, str] | None = None) -> str | None:
        """Check for redirects and return the final URL."""
        if url is None:
            return url
        try:
            async with httpx.AsyncClient(follow_redirects=False) as client:
                # Use GET with SSE headers instead of HEAD since many SSE servers don't support HEAD
                response = await client.get(url, timeout=2.0, headers={"Accept": "text/event-stream", **headers})
                if response.status_code == httpx.codes.TEMPORARY_REDIRECT:
                    return response.headers.get("Location", url)
                # Don't treat 404 as an error here - let the main connection handle it
        except (httpx.RequestError, httpx.HTTPError) as e:
            logger.warning(f"Error checking redirects: {e}")
        return url

    async def _connect_to_server(
        self,
        url: str | None,
        headers: dict[str, str] | None = None,
        timeout_seconds: int = 30,
        sse_read_timeout_seconds: int = 30,
    ) -> list[StructuredTool]:
        """Connect to MCP server using SSE transport (SDK style)."""
        # Validate and sanitize headers early
        validated_headers = _process_headers(headers)

        if url is None:
            msg = "URL is required for SSE mode"
            raise ValueError(msg)
        is_valid, error_msg = await self.validate_url(url, validated_headers)
        if not is_valid:
            msg = f"Invalid SSE URL ({url}): {error_msg}"
            raise ValueError(msg)

        url = await self.pre_check_redirect(url, validated_headers)

        # Store connection parameters for later use in run_tool
        self._connection_params = {
            "url": url,
            "headers": validated_headers,
            "timeout_seconds": timeout_seconds,
            "sse_read_timeout_seconds": sse_read_timeout_seconds,
        }

        # If no session context is set, create a default one
        if not self._session_context:
            # Generate a fallback context based on connection parameters
            import uuid

            param_hash = uuid.uuid4().hex[:8]
            self._session_context = f"default_sse_{param_hash}"

        # Get or create a persistent session
        session = await self._get_or_create_session()
        response = await session.list_tools()
        self._connected = True
        return response.tools

    async def connect_to_server(self, url: str, headers: dict[str, str] | None = None) -> list[StructuredTool]:
        """Connect to MCP server using SSE transport (SDK style)."""
        return await asyncio.wait_for(
            self._connect_to_server(url, headers), timeout=get_settings_service().settings.mcp_server_timeout
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
        return await session_manager.get_session(self._session_context, self._connection_params, "sse")

    async def disconnect(self):
        """Properly close the connection and clean up resources."""
        # Clean up session using session manager
        if self._session_context:
            session_manager = self._get_session_manager()
            await session_manager._cleanup_session(self._session_context)

        self.session = None
        self._connection_params = None
        self._connected = False
        self._session_context = None

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
            self._session_context = f"default_sse_{param_hash}"

        max_retries = 2
        last_error_type = None

        for attempt in range(max_retries):
            try:
                logger.debug(f"Attempting to run tool '{tool_name}' (attempt {attempt + 1}/{max_retries})")
                # Get or create persistent session
                session = await self._get_or_create_session()

                # Add timeout to prevent hanging
                import asyncio

                result = await asyncio.wait_for(
                    session.call_tool(tool_name, arguments=arguments),
                    timeout=30.0,  # 30 second timeout
                )
            except Exception as e:
                current_error_type = type(e).__name__
                logger.warning(f"Tool '{tool_name}' failed on attempt {attempt + 1}: {current_error_type} - {e}")

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
                    logger.error(f"Repeated {current_error_type} error for tool '{tool_name}', not retrying")
                    break

                last_error_type = current_error_type

                # If it's a connection error (ClosedResourceError or MCP connection closed) and we have retries left
                if (is_closed_resource_error or is_mcp_connection_error) and attempt < max_retries - 1:
                    logger.warning(
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
                    logger.warning(f"Tool '{tool_name}' timed out, retrying...")
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
                    logger.error(msg)
                    # Clean up failed session from cache
                    if self._session_context and self._component_cache:
                        cache_key = f"mcp_session_sse_{self._session_context}"
                        self._component_cache.delete(cache_key)
                    self._connected = False
                    raise ValueError(msg) from e
                # Re-raise unexpected errors
                raise
            else:
                logger.debug(f"Tool '{tool_name}' completed successfully")
                return result

        # This should never be reached due to the exception handling above
        msg = f"Failed to run tool '{tool_name}': Maximum retries exceeded with repeated {last_error_type} errors"
        logger.error(msg)
        raise ValueError(msg)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()


async def update_tools(
    server_name: str,
    server_config: dict,
    mcp_stdio_client: MCPStdioClient | None = None,
    mcp_sse_client: MCPSseClient | None = None,
) -> tuple[str, list[StructuredTool], dict[str, StructuredTool]]:
    """Fetch server config and update available tools."""
    if server_config is None:
        server_config = {}
    if not server_name:
        return "", [], {}
    if mcp_stdio_client is None:
        mcp_stdio_client = MCPStdioClient()
    if mcp_sse_client is None:
        mcp_sse_client = MCPSseClient()

    # Fetch server config from backend
    mode = "Stdio" if "command" in server_config else "SSE" if "url" in server_config else ""
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
    client: MCPStdioClient | MCPSseClient | None = None
    if mode == "Stdio":
        # Stdio connection
        args = server_config.get("args", [])
        env = server_config.get("env", {})
        full_command = " ".join([command, *args])
        tools = await mcp_stdio_client.connect_to_server(full_command, env)
        client = mcp_stdio_client
    elif mode == "SSE":
        # SSE connection
        tools = await mcp_sse_client.connect_to_server(url, headers=headers)
        client = mcp_sse_client
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

            tool_obj = StructuredTool(
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

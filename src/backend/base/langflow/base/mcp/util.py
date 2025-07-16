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

# MCP Session Manager constants
MAX_SESSIONS_PER_SERVER = 5  # Maximum number of sessions per server to prevent resource exhaustion
SESSION_IDLE_TIMEOUT = 300  # 5 minutes idle timeout for sessions
SESSION_CLEANUP_INTERVAL = 60  # Cleanup interval in seconds


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
        Processed dictionary
    """
    if headers is None:
        return {}
    if isinstance(headers, dict):
        return headers
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
        return processed_headers
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
    """Manages persistent MCP sessions with proper context manager lifecycle.

    Fixed version that addresses the memory leak issue by:
    1. Session reuse based on server identity rather than unique context IDs
    2. Maximum session limits per server to prevent resource exhaustion
    3. Idle timeout for automatic session cleanup
    4. Periodic cleanup of stale sessions
    """

    def __init__(self):
        # Structure: server_key -> {"sessions": {session_id: session_info}, "last_cleanup": timestamp}
        self.sessions_by_server = {}
        self._background_tasks = set()  # Keep references to background tasks
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
                await asyncio.sleep(SESSION_CLEANUP_INTERVAL)
                await self._cleanup_idle_sessions()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Error in periodic cleanup: {e}")

    async def _cleanup_idle_sessions(self):
        """Clean up sessions that have been idle for too long."""
        current_time = asyncio.get_event_loop().time()
        servers_to_remove = []

        for server_key, server_data in self.sessions_by_server.items():
            sessions = server_data.get("sessions", {})
            sessions_to_remove = []

            for session_id, session_info in sessions.items():
                if current_time - session_info["last_used"] > SESSION_IDLE_TIMEOUT:
                    sessions_to_remove.append(session_id)

            # Clean up idle sessions
            for session_id in sessions_to_remove:
                logger.info(f"Cleaning up idle session {session_id} for server {server_key}")
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
        elif transport_type == "sse":
            if isinstance(connection_params, dict) and "url" in connection_params:
                # Include URL and headers for uniqueness
                url = connection_params["url"]
                headers = str(sorted((connection_params.get("headers", {})).items()))
                key_input = f"{url}|{headers}"
                return f"sse_{hash(key_input)}"

        # Fallback to a generic key
        return f"{transport_type}_{hash(str(connection_params))}"

    async def _validate_session_connectivity(self, session) -> bool:
        """Validate that the session is actually usable by testing a simple operation."""
        try:
            response = await asyncio.wait_for(session.list_tools(), timeout=3.0)
            if response is None:
                return False
            tools = getattr(response, "tools", None)
            return tools is not None
        except Exception as e:
            logger.debug(f"Session connectivity test failed: {e}")
            return False

    async def get_session(self, context_id: str, connection_params, transport_type: str):
        """Get or create a session with improved reuse strategy.

        The key insight is that we should reuse sessions based on the server
        identity (command + args for stdio, URL for SSE) rather than the context_id.
        This prevents creating a new subprocess for each unique context.
        """
        server_key = self._get_server_key(connection_params, transport_type)

        # Ensure server entry exists
        if server_key not in self.sessions_by_server:
            self.sessions_by_server[server_key] = {"sessions": {}, "last_cleanup": asyncio.get_event_loop().time()}

        server_data = self.sessions_by_server[server_key]
        sessions = server_data["sessions"]

        # Try to find a healthy existing session
        for session_id, session_info in sessions.items():
            session = session_info["session"]
            task = session_info["task"]

            # Check if session is still alive
            if not task.done():
                # Update last used time
                session_info["last_used"] = asyncio.get_event_loop().time()

                # Quick health check
                if await self._validate_session_connectivity(session):
                    logger.debug(f"Reusing existing session {session_id} for server {server_key}")
                    return session
                logger.info(f"Session {session_id} for server {server_key} failed health check, cleaning up")
                await self._cleanup_session_by_id(server_key, session_id)
            else:
                # Task is done, clean up
                logger.info(f"Session {session_id} for server {server_key} task is done, cleaning up")
                await self._cleanup_session_by_id(server_key, session_id)

        # Check if we've reached the maximum number of sessions for this server
        if len(sessions) >= MAX_SESSIONS_PER_SERVER:
            # Remove the oldest session
            oldest_session_id = min(sessions.keys(), key=lambda x: sessions[x]["last_used"])
            logger.info(
                f"Maximum sessions reached for server {server_key}, removing oldest session {oldest_session_id}"
            )
            await self._cleanup_session_by_id(server_key, oldest_session_id)

        # Create new session
        session_id = f"{server_key}_{len(sessions)}"
        logger.info(f"Creating new session {session_id} for server {server_key}")

        if transport_type == "stdio":
            session, task = await self._create_stdio_session(session_id, connection_params)
        elif transport_type == "sse":
            session, task = await self._create_sse_session(session_id, connection_params)
        else:
            raise ValueError(f"Unknown transport type: {transport_type}")

        # Store session info
        sessions[session_id] = {
            "session": session,
            "task": task,
            "type": transport_type,
            "last_used": asyncio.get_event_loop().time(),
        }

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
                            logger.info(f"Session {session_id} is shutting down")
            except Exception as e:
                if not session_future.done():
                    session_future.set_exception(e)

        # Start the background task
        task = asyncio.create_task(session_task())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

        # Wait for session to be ready
        try:
            session = await asyncio.wait_for(session_future, timeout=10.0)
        except asyncio.TimeoutError as timeout_err:
            # Clean up the failed task
            if not task.done():
                task.cancel()
                import contextlib

                with contextlib.suppress(asyncio.CancelledError):
                    await task
            self._background_tasks.discard(task)
            msg = f"Timeout waiting for STDIO session {session_id} to initialize"
            logger.error(msg)
            raise ValueError(msg) from timeout_err

        return session, task

    async def _create_sse_session(self, session_id: str, connection_params):
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
                            logger.info(f"Session {session_id} is shutting down")
            except Exception as e:
                if not session_future.done():
                    session_future.set_exception(e)

        # Start the background task
        task = asyncio.create_task(session_task())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

        # Wait for session to be ready
        try:
            session = await asyncio.wait_for(session_future, timeout=10.0)
        except asyncio.TimeoutError as timeout_err:
            # Clean up the failed task
            if not task.done():
                task.cancel()
                import contextlib

                with contextlib.suppress(asyncio.CancelledError):
                    await task
            self._background_tasks.discard(task)
            msg = f"Timeout waiting for SSE session {session_id} to initialize"
            logger.error(msg)
            raise ValueError(msg) from timeout_err

        return session, task

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
            # Cancel the background task which will properly close the session
            if "task" in session_info:
                task = session_info["task"]
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        logger.info(f"Cancelled task for session {session_id}")
        except Exception as e:
            logger.warning(f"Error cleaning up session {session_id}: {e}")
        finally:
            # Remove from sessions dict
            del sessions[session_id]

    async def cleanup_all(self):
        """Clean up all sessions."""
        # Cancel periodic cleanup task
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

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

        # Clear all background tasks
        for task in list(self._background_tasks):
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    async def _cleanup_session(self, context_id: str):
        """Compatibility method for the old session cleanup interface.

        This method provides backward compatibility for client code that calls
        _cleanup_session(context_id) instead of the new _cleanup_session_by_id(server_key, session_id).

        Since the new session manager doesn't maintain a context_id -> session mapping,
        we clean up all sessions that might be associated with this context.
        """
        # In the old system, context_id was used as the session key
        # In the new system, we need to find sessions that might be using this context

        # The safest approach is to clean up all sessions since we can't reliably
        # map context_id to the specific session in the new structure
        logger.debug(f"Cleaning up sessions for context_id: {context_id}")

        # For backward compatibility, we'll clean up all sessions
        # This is safe because:
        # 1. Sessions are designed to be recreated on demand
        # 2. The old behavior was to clean up on disconnect anyway
        # 3. Multiple contexts can share the same session in the new system
        await self.cleanup_all()


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

    async def validate_url(self, url: str | None) -> tuple[bool, str]:
        """Validate the SSE URL before attempting connection."""
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return False, "Invalid URL format. Must include scheme (http/https) and host."

            async with httpx.AsyncClient() as client:
                try:
                    # For SSE endpoints, try a GET request with short timeout
                    # Many SSE servers don't support HEAD requests and return 404
                    response = await client.get(url, timeout=2.0, headers={"Accept": "text/event-stream"})

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

    async def pre_check_redirect(self, url: str | None) -> str | None:
        """Check for redirects and return the final URL."""
        if url is None:
            return url
        try:
            async with httpx.AsyncClient(follow_redirects=False) as client:
                # Use GET with SSE headers instead of HEAD since many SSE servers don't support HEAD
                response = await client.get(url, timeout=2.0, headers={"Accept": "text/event-stream"})
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
        if headers is None:
            headers = {}
        if url is None:
            msg = "URL is required for SSE mode"
            raise ValueError(msg)
        is_valid, error_msg = await self.validate_url(url)
        if not is_valid:
            msg = f"Invalid SSE URL ({url}): {error_msg}"
            raise ValueError(msg)

        url = await self.pre_check_redirect(url)

        # Store connection parameters for later use in run_tool
        self._connection_params = {
            "url": url,
            "headers": headers,
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

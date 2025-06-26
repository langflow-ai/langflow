import asyncio
import os
import platform
import shutil
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

import httpx
from httpx import codes as httpx_codes
from langchain_core.tools import StructuredTool
from langflow.services.deps import get_settings_service
from loguru import logger
from mcp import ClientSession
from pydantic import BaseModel, Field, create_model
from sqlmodel import select

from langflow.services.database.models.flow.model import Flow

HTTP_ERROR_STATUS_CODE = httpx_codes.BAD_REQUEST  # HTTP status code for client errors
NULLABLE_TYPE_LENGTH = 2  # Number of types in a nullable union (the type itself + null)


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
        this_flow_name = flow.action_name if is_action and flow.action_name else "_".join(flow.name.lower().split())
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


class MCPStdioClient:
    def __init__(self):
        self.session: ClientSession | None = None
        self._connection_params = None
        self._connected = False

    async def _connect_to_server(self, command_str: str, env: dict[str, str] | None = None) -> list[StructuredTool]:
        """Connect to MCP server using stdio transport (SDK style)."""
        from mcp import StdioServerParameters
        from mcp.client.stdio import stdio_client

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

        try:
            async with stdio_client(server_params) as (read, write), ClientSession(read, write) as session:
                await session.initialize()
                response = await session.list_tools()
                self._connected = True
                return response.tools
        except (ConnectionError, TimeoutError, OSError, ValueError) as e:
            logger.error(f"Failed to connect to MCP stdio server: {e}")
            self._connection_params = None
            self._connected = False
            return []

    async def connect_to_server(self, command_str: str, env: dict[str, str] | None = None) -> list[StructuredTool]:
        """Connect to MCP server using stdio transport (SDK style)."""
        try:
            return await asyncio.wait_for(
                self._connect_to_server(command_str, env), timeout=get_settings_service().settings.mcp_server_timeout
            )
        except (ConnectionError, TimeoutError, OSError, ValueError) as e:
            logger.error(f"Failed to connect to MCP stdio server: {e}")
            self._connection_params = None
            self._connected = False
            return []

    async def disconnect(self):
        """Properly close the connection and clean up resources."""
        self.session = None
        self._connection_params = None
        self._connected = False

    async def run_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Run a tool with the given arguments.

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

        try:
            from mcp.client.stdio import stdio_client

            async with stdio_client(self._connection_params) as (read, write), ClientSession(read, write) as session:
                await session.initialize()
                return await session.call_tool(tool_name, arguments=arguments)
        except (ConnectionError, TimeoutError, OSError, ValueError) as e:
            msg = f"Failed to run tool '{tool_name}': {e}"
            logger.error(msg)
            # Mark as disconnected on error
            self._connected = False
            raise ValueError(msg) from e

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()


class MCPSseClient:
    def __init__(self):
        self.session: ClientSession | None = None
        self._connection_params = None
        self._connected = False

    async def validate_url(self, url: str | None) -> tuple[bool, str]:
        """Validate the SSE URL before attempting connection."""
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return False, "Invalid URL format. Must include scheme (http/https) and host."

            async with httpx.AsyncClient() as client:
                try:
                    # First try a HEAD request to check if server is reachable
                    response = await client.head(url, timeout=5.0)
                    if response.status_code >= HTTP_ERROR_STATUS_CODE:
                        return False, f"Server returned error status: {response.status_code}"

                except httpx.TimeoutException:
                    return False, "Connection timed out. Server may be down or unreachable."
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
                response = await client.request("HEAD", url)
                if response.status_code == httpx.codes.TEMPORARY_REDIRECT:
                    return response.headers.get("Location", url)
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
        from mcp.client.sse import sse_client

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

        try:
            async with (
                sse_client(url, headers, timeout_seconds, sse_read_timeout_seconds) as (read, write),
                ClientSession(read, write) as session,
            ):
                await session.initialize()
                response = await session.list_tools()
                self._connected = True
                return response.tools
        except (ConnectionError, TimeoutError, OSError, ValueError) as e:
            logger.error(f"Failed to connect to MCP SSE server: {e}")
            self._connection_params = None
            self._connected = False
            return []

    async def connect_to_server(self, url: str, headers: dict[str, str] | None = None) -> list[StructuredTool]:
        """Connect to MCP server using SSE transport (SDK style)."""
        try:
            return await asyncio.wait_for(
                self._connect_to_server(url, headers), timeout=get_settings_service().settings.mcp_server_timeout
            )
        except (ConnectionError, TimeoutError, OSError, ValueError) as e:
            logger.error(f"Failed to connect to MCP SSE server: {e}")
            self._connection_params = None
            self._connected = False
            return []

    async def disconnect(self):
        """Properly close the connection and clean up resources."""
        self.session = None
        self._connection_params = None
        self._connected = False

    async def run_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Run a tool with the given arguments.

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

        try:
            from mcp.client.sse import sse_client

            params = self._connection_params
            async with (
                sse_client(
                    params["url"], params["headers"], params["timeout_seconds"], params["sse_read_timeout_seconds"]
                ) as (read, write),
                ClientSession(read, write) as session,
            ):
                await session.initialize()
                return await session.call_tool(tool_name, arguments=arguments)
        except (ConnectionError, TimeoutError, OSError, ValueError) as e:
            msg = f"Failed to run tool '{tool_name}': {e}"
            logger.error(msg)
            # Mark as disconnected on error
            self._connected = False
            raise ValueError(msg) from e

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

    try:
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
            return "", [], {}

        # Determine connection type and parameters
        client: MCPStdioClient | MCPSseClient | None = None
        try:
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
        except (ConnectionError, TimeoutError, OSError, ValueError) as e:
            logger.error(f"Failed to connect to MCP server '{server_name}': {e}")
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
    except (ConnectionError, TimeoutError, OSError, ValueError, AttributeError, AssertionError) as e:
        logger.error(f"Unexpected error while updating tools for MCP server '{server_name}': {e}")
        return "", [], {}
    else:
        return mode, tool_list, tool_cache

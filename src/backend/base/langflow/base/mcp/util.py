from __future__ import annotations

import asyncio
import re
import shutil
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

from httpx import codes as httpx_codes
from langchain_core.tools import StructuredTool
from loguru import logger
from pydantic import BaseModel, Field, create_model
from sqlmodel import select

# Import clients from their respective modules
from langflow.base.mcp.sse_client import MCPSseClient
from langflow.base.mcp.stdio_client import MCPStdioClient
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
    """Validate the npx command using word boundaries to avoid false positives."""
    if re.search(r"\bnpx\b", command) and not shutil.which("node"):
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


async def update_tools(
    server_name: str,
    server_config: dict,
    mcp_stdio_client: MCPStdioClient | None = None,
    mcp_sse_client: MCPSseClient | None = None,
) -> tuple[str, list[StructuredTool], dict[str, StructuredTool], dict[str, Any]]:
    """Fetch server config and update available tools.

    Returns:
        Tuple containing:
        - mode: Connection mode ("Stdio" or "SSE")
        - tool_list: List of structured tools
        - tool_cache: Dictionary mapping tool names to tools
        - protocol_info: Protocol version and connection details
    """
    if server_config is None:
        server_config = {}
    if not server_name:
        return "", [], {}, {}
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
            return "", [], {}, {}

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
                return "", [], {}, {}
        except (ConnectionError, TimeoutError, OSError, ValueError) as e:
            logger.error(f"Failed to connect to MCP server '{server_name}': {e}")
            return "", [], {}, {}

        if not tools or not client or not client._connected:
            logger.warning(f"No tools available from MCP server '{server_name}' or connection failed")
            return "", [], {}, {}

        # Capture protocol information from the connected client
        protocol_info = {}
        if client and hasattr(client, "get_protocol_info"):
            protocol_info = client.get_protocol_info()
            logger.debug(f"Retrieved protocol info for '{server_name}': {protocol_info}")

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
                continue

        logger.info(f"Successfully loaded {len(tool_list)} tools from MCP server '{server_name}'")
    except (ConnectionError, TimeoutError, OSError, ValueError) as e:
        logger.error(f"Unexpected error while updating tools for MCP server '{server_name}': {e}")
        return "", [], {}, {}
    else:
        return mode, tool_list, tool_cache, protocol_info

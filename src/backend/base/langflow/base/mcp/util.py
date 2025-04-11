import asyncio
import os
import re
from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack
from datetime import date
from enum import Enum
from typing import Any, Union
from urllib.parse import urlparse
from uuid import UUID

import httpx
from httpx import codes as httpx_codes
from loguru import logger
from mcp import ClientSession, StdioServerParameters, stdio_client
from mcp.client.sse import sse_client
from pydantic import Field, create_model
from sqlmodel import select

from langflow.helpers.base_model import BaseModel
from langflow.services.database.models import Flow

HTTP_ERROR_STATUS_CODE = httpx_codes.BAD_REQUEST  # HTTP status code for client errors


def create_tool_coroutine(tool_name: str, arg_schema: type[BaseModel], session) -> Callable[..., Awaitable]:
    async def tool_coroutine(*args, **kwargs):
        # Get field names from the model (preserving order)
        field_names = list(arg_schema.__fields__.keys())
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
            validated = arg_schema.parse_obj(provided_args)
        except Exception as e:
            msg = f"Invalid input: {e}"
            raise ValueError(msg) from e
        return await session.call_tool(tool_name, arguments=validated.dict())

    return tool_coroutine


def create_tool_func(tool_name: str, arg_schema: type[BaseModel], session) -> Callable[..., str]:
    def tool_func(*args, **kwargs):
        field_names = list(arg_schema.__fields__.keys())
        provided_args = {}
        for i, arg in enumerate(args):
            if i >= len(field_names):
                msg = "Too many positional arguments provided"
                raise ValueError(msg)
            provided_args[field_names[i]] = arg
        provided_args.update(kwargs)
        try:
            validated = arg_schema.parse_obj(provided_args)
        except Exception as e:
            msg = f"Invalid input: {e}"
            raise ValueError(msg) from e
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(session.call_tool(tool_name, arguments=validated.dict()))

    return tool_func


async def get_flow_snake_case(flow_name: str, user_id: str, session) -> Flow | None:
    uuid_user_id = UUID(user_id) if isinstance(user_id, str) else user_id
    stmt = select(Flow).where(Flow.user_id == uuid_user_id).where(Flow.is_component == False)  # noqa: E712
    flows = (await session.exec(stmt)).all()

    for flow in flows:
        this_flow_name = "_".join(flow.name.lower().split())
        if this_flow_name == flow_name:
            return flow
    return None


def create_input_schema_from_json_schema(
    schema: dict[str, Any],
    defs: dict[str, Any] | None = None,
    *,
    keep_title: bool = False,
) -> type[BaseModel]:
    """Converts a JSON schema into a Pydantic model dynamically.

    Fields not listed as required are wrapped in Optional[...] and default to None if not provided.

    :param schema: The JSON schema as a dictionary.
    :return: A Pydantic model class.
    """
    if schema.get("type") != "object":
        msg = "JSON schema must be of type 'object' at the root level."
        raise ValueError(msg)

    if defs is None:
        defs = {}

    defs_to_process = schema.get("$defs", {})

    # Parse enum definitions first since they always have plain schema
    enum_defs: dict[str, Any] = {}
    for name, enum_def in defs_to_process.items():
        if "enum" in enum_def:
            enum_members = {re.sub(r"\W|^(?=\d)", "_", v): v for v in enum_def["enum"]}
            enum_defs[name] = Enum(name, enum_members)

    defs.update(enum_defs)

    for def_name in defs:
        # Drop already processed defs as we might need those to resolve chained references
        defs_to_process.pop(def_name, None)

    # Parse all the other definitions recursively
    for name, _def in defs_to_process.items():
        if "enum" not in _def:
            # In order to resolve potential complex references we can pass unprocessed definitions further
            # Still, it can't really resolve circular references, only chained ones
            possibly_needed_defs = {k: v for k, v in defs_to_process.items() if k != name}
            _def["$defs"] = possibly_needed_defs
            defs[name] = create_input_schema_from_json_schema(_def, defs, keep_title=True)

    def _resolve_type(definition: dict) -> Any:
        if "$ref" in definition:
            ref_name = definition["$ref"].split("/")[-1]
            return defs.get(ref_name, str)  # defaults to str

        # anyOf should go first since complex objects can have both anyOf and `type: object``
        if "anyOf" in definition:
            subtypes = [_resolve_type(sub) for sub in definition["anyOf"]]
            subtypes = list(set(subtypes))  # remove duplicates
            if type(None) in subtypes:
                subtypes.remove(type(None))
                if len(subtypes) == 1:
                    return subtypes[0] | None
                return Union[tuple(subtypes)] | None  # noqa: UP007
            return Union[tuple(subtypes)]  # noqa: UP007

        if "type" in definition:
            field_type_str = definition.get("type", "str")

            if field_type_str in ("string", "str"):
                if definition.get("format") == "date":
                    return date
                return str
            if field_type_str in ("integer", "int"):
                return int
            if field_type_str in ("number", "float"):
                return float
            if field_type_str in ("boolean", "bool"):
                return bool
            if field_type_str == "object":
                # we can't handle dict reverse parsing properly since `dict key` typing is not inherited from the schema
                return dict
            if field_type_str == "array":
                # Case: array = list
                if "items" in definition:
                    item_type = _resolve_type(definition["items"])
                    return list[item_type]  # type: ignore # noqa: PGH003
                # Case: array = tuple
                if "prefixItems" in definition:
                    item_types = [_resolve_type(_item) for _item in definition["prefixItems"]]
                    return tuple[*item_types]  # type: ignore # noqa: PGH003
                return list[str]  # fallback to list of strings
            if field_type_str == "null":
                return type(None)

        return Any  # fallback for anything unrecognized

    fields = {}
    properties = schema.get("properties", {})

    for field_name, field_def in properties.items():
        base_type = _resolve_type(field_def)

        field_metadata = {
            "description": field_def.get("description", ""),
            "required": field_def.get("required", False),
        }
        if "annotation" in field_def:
            field_metadata["annotation"] = field_def.get("annotation")

        # For non-required fields, wrap the type in Optional[...] and set a default value.
        if "default" in field_def or not field_metadata["required"]:
            field_metadata["default"] = field_def.get("default", None)

        fields[field_name] = (base_type, Field(**field_metadata))

    if keep_title:
        return create_model(schema.get("title", "UnknownType"), **fields)
    return create_model("InputSchema", **fields)


class MCPStdioClient:
    def __init__(self):
        self.session: ClientSession | None = None
        self.exit_stack = AsyncExitStack()

    async def connect_to_server(self, command_str: str):
        command = command_str.split(" ")
        server_params = StdioServerParameters(
            command=command[0],
            args=command[1:],
            env={"DEBUG": "true", "PATH": os.environ["PATH"]},
        )
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))
        await self.session.initialize()
        response = await self.session.list_tools()
        return response.tools


class MCPSseClient:
    def __init__(self):
        self.write = None
        self.sse = None
        self.session: ClientSession | None = None
        self.exit_stack = AsyncExitStack()
        self.max_retries = 3
        self.retry_delay = 1.0  # seconds

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

    async def _connect_with_timeout(
        self, url: str | None, headers: dict[str, str] | None, timeout_seconds: int, sse_read_timeout_seconds: int
    ):
        """Attempt to connect with timeout."""
        try:
            if url is None:
                return
            sse_transport = await self.exit_stack.enter_async_context(
                sse_client(url, headers, timeout_seconds, sse_read_timeout_seconds)
            )
            self.sse, self.write = sse_transport
            self.session = await self.exit_stack.enter_async_context(ClientSession(self.sse, self.write))
            await self.session.initialize()
        except Exception as e:
            msg = f"Failed to establish SSE connection: {e!s}"
            raise ConnectionError(msg) from e

    async def connect_to_server(
        self,
        url: str | None,
        headers: dict[str, str] | None,
        timeout_seconds: int = 30,
        sse_read_timeout_seconds: int = 30,
    ):
        """Connect to server with retries and improved error handling."""
        if headers is None:
            headers = {}

        # First validate the URL
        is_valid, error_msg = await self.validate_url(url)
        if not is_valid:
            msg = f"Invalid SSE URL ({url}): {error_msg}"
            raise ValueError(msg)

        url = await self.pre_check_redirect(url)
        last_error = None

        for attempt in range(self.max_retries):
            try:
                await asyncio.wait_for(
                    self._connect_with_timeout(url, headers, timeout_seconds, sse_read_timeout_seconds),
                    timeout=timeout_seconds,
                )

                if self.session is None:
                    msg = "Session not initialized"
                    raise ValueError(msg)

                response = await self.session.list_tools()

            except asyncio.TimeoutError:
                last_error = f"Connection to {url} timed out after {timeout_seconds} seconds"
                logger.warning(f"Connection attempt {attempt + 1} failed: {last_error}")
            except ConnectionError as err:
                last_error = str(err)
                logger.warning(f"Connection attempt {attempt + 1} failed: {last_error}")
            except (ValueError, httpx.HTTPError, OSError) as err:
                last_error = f"Connection error: {err!s}"
                logger.warning(f"Connection attempt {attempt + 1} failed: {last_error}")
            else:
                return response.tools

            if attempt < self.max_retries - 1:
                await asyncio.sleep(self.retry_delay * (attempt + 1))

        msg = f"Failed to connect after {self.max_retries} attempts. Last error: {last_error}"
        raise ConnectionError(msg)

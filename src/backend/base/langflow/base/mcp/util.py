import asyncio
import os
from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack
from typing import Any
from uuid import UUID

import httpx
from mcp import ClientSession, StdioServerParameters, stdio_client
from mcp.client.sse import sse_client
from pydantic import Field, create_model
from sqlmodel import select

from langflow.helpers.base_model import BaseModel
from langflow.services.database.models import Flow


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


async def get_flow(flow_name: str, user_id: str, session) -> Flow | None:
    uuid_user_id = UUID(user_id) if isinstance(user_id, str) else user_id
    stmt = select(Flow).where(Flow.user_id == uuid_user_id).where(Flow.is_component == False)  # noqa: E712
    flows = (await session.exec(stmt)).all()

    for flow in flows:
        if flow.to_data().name == flow_name:
            return flow
    return None


def create_input_schema_from_json_schema(schema: dict[str, Any]) -> type[BaseModel]:
    """Converts a JSON schema into a Pydantic model dynamically.

    Fields not listed as required are wrapped in Optional[...] and default to None if not provided.

    :param schema: The JSON schema as a dictionary.
    :return: A Pydantic model class.
    """
    if schema.get("type") != "object":
        msg = "JSON schema must be of type 'object' at the root level."
        raise ValueError(msg)

    fields = {}
    properties = schema.get("properties", {})
    required_fields = set(schema.get("required", []))

    for field_name, field_def in properties.items():
        # Determine the base type from the JSON schema type string.
        field_type_str = field_def.get("type", "str")  # Defaults to string if not specified.
        base_type = {
            "string": str,
            "str": str,
            "integer": int,
            "int": int,
            "number": float,
            "boolean": bool,
            "array": list,
            "object": dict,
        }.get(field_type_str, Any)

        field_metadata = {"description": field_def.get("description", "")}

        # For non-required fields, wrap the type in Optional[...] and set a default value.
        if field_name not in required_fields:
            field_metadata["default"] = field_def.get("default", None)

        fields[field_name] = (base_type, Field(**field_metadata))

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

    async def pre_check_redirect(self, url: str):
        async with httpx.AsyncClient(follow_redirects=False) as client:
            response = await client.request("HEAD", url)
            if response.status_code == httpx.codes.TEMPORARY_REDIRECT:
                return response.headers.get("Location")
        return url

    async def _connect_with_timeout(
        self, url: str, headers: dict[str, str] | None, timeout_seconds: int, sse_read_timeout_seconds: int
    ):
        sse_transport = await self.exit_stack.enter_async_context(
            sse_client(url, headers, timeout_seconds, sse_read_timeout_seconds)
        )
        self.sse, self.write = sse_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.sse, self.write))
        await self.session.initialize()

    async def connect_to_server(
        self, url: str, headers: dict[str, str] | None, timeout_seconds: int = 500, sse_read_timeout_seconds: int = 500
    ):
        if headers is None:
            headers = {}
        url = await self.pre_check_redirect(url)
        try:
            await asyncio.wait_for(
                self._connect_with_timeout(url, headers, timeout_seconds, sse_read_timeout_seconds),
                timeout=timeout_seconds,
            )
            if self.session is None:
                msg = "Session not initialized"
                raise ValueError(msg)
            response = await self.session.list_tools()
        except asyncio.TimeoutError as err:
            msg = f"Connection to {url} timed out after {timeout_seconds} seconds"
            raise TimeoutError(msg) from err
        return response.tools

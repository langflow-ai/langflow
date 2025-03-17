# from langflow.field_typing import Data
import asyncio
from contextlib import AsyncExitStack

import httpx
from mcp import ClientSession, types
from mcp.client.sse import sse_client

from langflow.base.mcp.util import create_tool_coroutine, create_tool_func
from langflow.components.tools.mcp_stdio import create_input_schema_from_json_schema
from langflow.custom import Component
from langflow.field_typing import Tool
from langflow.io import MessageTextInput, Output

# Define constant for status code
HTTP_TEMPORARY_REDIRECT = 307


class MCPSseClient:
    def __init__(self):
        # Initialize session and client objects
        self.write = None
        self.sse = None
        self.session: ClientSession | None = None
        self.exit_stack = AsyncExitStack()

    async def pre_check_redirect(self, url: str):
        """Check if the URL responds with a 307 Redirect."""
        async with httpx.AsyncClient(follow_redirects=False) as client:
            response = await client.request("HEAD", url)
            if response.status_code == HTTP_TEMPORARY_REDIRECT:
                return response.headers.get("Location")  # Return the redirect URL
        return url  # Return the original URL if no redirect

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
            # List available tools
            if self.session is None:
                msg = "Session not initialized"
                raise ValueError(msg)
            response = await self.session.list_tools()
        except asyncio.TimeoutError as err:
            error_message = f"Connection to {url} timed out after {timeout_seconds} seconds"
            raise TimeoutError(error_message) from err
        else:  # Only executed if no TimeoutError
            return response.tools

    async def _connect_with_timeout(
        self, url: str, headers: dict[str, str] | None, timeout_seconds: int, sse_read_timeout_seconds: int
    ):
        sse_transport = await self.exit_stack.enter_async_context(
            sse_client(url, headers, timeout_seconds, sse_read_timeout_seconds)
        )
        self.sse, self.write = sse_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.sse, self.write))
        await self.session.initialize()


class MCPSse(Component):
    client = MCPSseClient()
    tools = types.ListToolsResult
    tool_names = [str]
    display_name = "MCP Tools (SSE)"
    description = "Connects to an MCP server over SSE and exposes it's tools as langflow tools to be used by an Agent."
    documentation: str = "https://docs.langflow.org/components-custom-components"
    icon = "code"
    name = "MCPSse"

    inputs = [
        MessageTextInput(
            name="url",
            display_name="mcp sse url",
            info="sse url",
            value="http://localhost:7860/api/v1/mcp/sse",
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(display_name="Tools", name="tools", method="build_output"),
    ]

    async def build_output(self) -> list[Tool]:
        if self.client.session is None:
            self.tools = await self.client.connect_to_server(self.url, {})

        tool_list = []

        for tool in self.tools:
            args_schema = create_input_schema_from_json_schema(tool.inputSchema)
            tool_list.append(
                Tool(
                    name=tool.name,  # maybe format this
                    description=tool.description,
                    args_schema=args_schema,
                    coroutine=create_tool_coroutine(tool.name, args_schema, self.client.session),
                    func=create_tool_func(tool.name, self.client.session),
                )
            )

        self.tool_names = [tool.name for tool in self.tools]
        return tool_list

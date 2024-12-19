# from langflow.field_typing import Data
from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack

import httpx
from dotenv import load_dotenv
from langchain_core.tools import StructuredTool
from mcp import ClientSession
from mcp.client.sse import sse_client

from langflow.components.tools.mcp_stdio import create_input_schema_from_json_schema
from langflow.custom import Component
from langflow.io import MessageTextInput, Output

load_dotenv()  # load environment variables from .env

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
        self, url: str, headers: dict[str, str] | None, timeout: int = 500, sse_read_timeout: int = 500
    ):
        if headers is None:
            headers = {}
        url = await self.pre_check_redirect(url)
        sse_transport = await self.exit_stack.enter_async_context(sse_client(url, headers, timeout, sse_read_timeout))
        self.sse, self.write = sse_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.sse, self.write))

        await self.session.initialize()

        # List available tools
        response = await self.session.list_tools()
        return response.tools


class MCPSse(Component):
    client = MCPSseClient()
    tools = None
    tool_names = []
    display_name = "MCP Tools (SSE)"
    description = "Use as a template to create your own component."
    documentation: str = "http://docs.langflow.org/components/custom"
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
        Output(display_name="Output", name="output", method="build_output"),
    ]

    def create_tool_coroutine(self, tool_name: str) -> Callable[[dict], Awaitable]:
        async def tool_coroutine(**kwargs):
            return await self.client.session.call_tool(tool_name, arguments=kwargs)

        return tool_coroutine

    async def build_output(self) -> list[StructuredTool]:
        if self.client.session is None:
            self.tools = await self.client.connect_to_server(self.url)

        tool_list = []

        for tool in self.tools:
            args_schema = create_input_schema_from_json_schema(tool.inputSchema)
            callbacks = self.get_langchain_callbacks()
            tool_list.append(
                StructuredTool(
                    name=tool.name,  # maybe format this
                    description=tool.description,
                    coroutine=self.create_tool_coroutine(tool.name),
                    args_schema=args_schema,
                    # args_schema=DataSchema,
                    handle_tool_error=True,
                    callbacks=callbacks,
                )
            )

        self.tool_names = [tool.name for tool in self.tools]
        return tool_list

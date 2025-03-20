import asyncio
import os
from contextlib import AsyncExitStack

import httpx
from langchain_core.tools import StructuredTool
from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.client.stdio import StdioServerParameters, stdio_client

from langflow.base.mcp.util import (
    create_input_schema_from_json_schema,
    create_tool_coroutine,
    create_tool_func,
)
from langflow.custom import Component
from langflow.field_typing import Tool
from langflow.io import DropdownInput, MessageTextInput, Output

# Define constant for status code
HTTP_TEMPORARY_REDIRECT = 307


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
            if response.status_code == HTTP_TEMPORARY_REDIRECT:
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


class MCPTools(Component):
    stdio_client = MCPStdioClient()
    sse_client = MCPSseClient()
    tools = []  # Will hold the list of available tools
    tool_names = [str]

    display_name = "MCP Tools"
    description = (
        "Connects to an MCP server over stdio or SSE and exposes its tools as langflow tools to be used by an Agent."
    )
    documentation: str = "https://docs.langflow.org/components-custom-components"
    icon = "code"
    name = "MCPTools"

    inputs = [
        DropdownInput(
            name="mode",
            display_name="Mode",
            options=["Stdio", "SSE"],
            info="Select the connection mode",
            real_time_refresh=True,
        ),
        MessageTextInput(
            name="command",
            display_name="MCP Command",
            info="Command for MCP stdio connection",
            value="uvx mcp-sse-shim@latest",
            tool_mode=True,
            show=True,  # Shown when mode is Stdio
        ),
        MessageTextInput(
            name="url",
            display_name="MCP SSE URL",
            info="URL for MCP SSE connection",
            value="http://localhost:7860/api/v1/mcp/sse",
            tool_mode=True,
            show=False,  # Shown when mode is SSE
        ),
    ]

    outputs = [
        Output(display_name="Tools", name="tools", method="build_output"),
    ]

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None) -> dict:
        """Toggle the visibility of connection-specific fields based on the selected mode."""
        if field_name == "mode":
            if field_value == "Stdio":
                build_config["command"]["show"] = True
                build_config["url"]["show"] = False
            elif field_value == "SSE":
                build_config["command"]["show"] = False
                build_config["url"]["show"] = True
        return build_config

    async def build_output(self) -> list[Tool]:
        """Connect to the MCP server using the selected mode and return available tools as StructuredTool instances."""
        if self.mode == "Stdio":
            if self.stdio_client.session is None:
                self.tools = await self.stdio_client.connect_to_server(self.command)
        elif self.mode == "SSE":
            if self.sse_client.session is None:
                self.tools = await self.sse_client.connect_to_server(self.url, {})
        else:
            msg = "Invalid mode selected."
            raise ValueError(msg)

        tool_list = []
        for tool in self.tools:
            args_schema = create_input_schema_from_json_schema(tool.inputSchema)
            if self.mode == "Stdio":
                tool_list.append(
                    StructuredTool(
                        name=tool.name,
                        description=tool.description,
                        args_schema=args_schema,
                        func=create_tool_func(tool.name, args_schema, self.stdio_client.session),
                        coroutine=create_tool_coroutine(tool.name, args_schema, self.stdio_client.session),
                    )
                )
            elif self.mode == "SSE":
                tool_list.append(
                    StructuredTool(
                        name=tool.name,
                        description=tool.description,
                        args_schema=args_schema,
                        func=create_tool_func(tool.name, args_schema, self.sse_client.session),
                        coroutine=create_tool_coroutine(tool.name, args_schema, self.sse_client.session),
                    )
                )
        self.tool_names = [tool.name for tool in self.tools]
        return tool_list

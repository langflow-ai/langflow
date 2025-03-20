# from langflow.field_typing import Data
import os
from contextlib import AsyncExitStack

from langchain_core.tools import StructuredTool
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client

from langflow.base.mcp.util import create_input_schema_from_json_schema, create_tool_coroutine, create_tool_func
from langflow.custom import Component
from langflow.field_typing import Tool
from langflow.io import MessageTextInput, Output


class MCPStdioClient:
    def __init__(self):
        # Initialize session and client objects
        self.session: ClientSession | None = None
        self.exit_stack = AsyncExitStack()

    async def connect_to_server(self, command_str: str):
        command = command_str.split(" ")
        server_params = StdioServerParameters(
            command=command[0], args=command[1:], env={"DEBUG": "true", "PATH": os.environ["PATH"]}
        )

        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))

        await self.session.initialize()

        # List available tools
        response = await self.session.list_tools()
        return response.tools


class MCPStdio(Component):
    client = MCPStdioClient()
    tools = types.ListToolsResult
    tool_names = [str]
    display_name = "MCP Tools (stdio)"
    description = (
        "Connects to an MCP server over stdio and exposes it's tools as langflow tools to be used by an Agent."
    )
    documentation: str = "https://docs.langflow.org/components-custom-components"
    icon = "code"
    name = "MCPStdio"

    inputs = [
        MessageTextInput(
            name="command",
            display_name="mcp command",
            info="mcp command",
            value="uvx mcp-sse-shim@latest",
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(display_name="Tools", name="tools", method="build_output"),
    ]

    async def build_output(self) -> list[Tool]:
        if self.client.session is None:
            self.tools = await self.client.connect_to_server(self.command)

        tool_list = []

        for tool in self.tools:
            args_schema = create_input_schema_from_json_schema(tool.inputSchema)
            tool_list.append(
                StructuredTool(
                    name=tool.name,
                    description=tool.description,
                    args_schema=args_schema,
                    func=create_tool_func(tool.name, args_schema),
                    coroutine=create_tool_coroutine(tool.name, args_schema, self.client.session),
                )
            )
        self.tool_names = [tool.name for tool in self.tools]
        return tool_list

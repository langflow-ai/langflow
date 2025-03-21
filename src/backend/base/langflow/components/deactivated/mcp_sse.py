# from langflow.field_typing import Data

from langchain_core.tools import StructuredTool
from mcp import types

from langflow.base.mcp.util import (
    MCPSseClient,
    create_input_schema_from_json_schema,
    create_tool_coroutine,
    create_tool_func,
)
from langflow.custom import Component
from langflow.field_typing import Tool
from langflow.io import MessageTextInput, Output


class MCPSse(Component):
    client = MCPSseClient()
    tools = types.ListToolsResult
    tool_names = [str]
    display_name = "MCP Tools (SSE) [DEPRECATED]"
    description = "Connects to an MCP server over SSE and exposes it's tools as langflow tools to be used by an Agent."
    documentation: str = "https://docs.langflow.org/components-custom-components"
    icon = "code"
    name = "MCPSse"
    legacy = True

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
                StructuredTool(
                    name=tool.name,  # maybe format this
                    description=tool.description,
                    args_schema=args_schema,
                    func=create_tool_func(tool.name, args_schema, self.client.session),
                    coroutine=create_tool_coroutine(tool.name, args_schema, self.client.session),
                )
            )

        self.tool_names = [tool.name for tool in self.tools]
        return tool_list

# from lfx.field_typing import Data

import shlex

from langchain_core.tools import StructuredTool
from mcp import types

from lfx.base.mcp.security import validate_mcp_stdio_config
from lfx.base.mcp.util import (
    MCPStdioClient,
    create_input_schema_from_json_schema,
    create_tool_coroutine,
    create_tool_func,
)
from lfx.custom.custom_component.component import Component
from lfx.field_typing import Tool
from lfx.io import MessageTextInput, Output


class MCPStdio(Component):
    client = MCPStdioClient()
    tools = types.ListToolsResult
    tool_names = [str]
    display_name = "MCP Tools (stdio) [DEPRECATED]"
    description = (
        "Connects to an MCP server over stdio and exposes it's tools as langflow tools to be used by an Agent."
    )
    documentation: str = "https://docs.langflow.org/components-custom-components"
    icon = "code"
    name = "MCPStdio"
    legacy = True

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
            # SECURITY: ``self.command`` is tenant-controlled and is passed straight to a
            # ``bash -c "exec <command>"`` stdio transport. This legacy component bypasses the
            # update_tools choke point, so enforce the MCP command allowlist/metacharacter
            # policy here too. Raises MCPStdioSecurityError (a ValueError) on violation.
            command_parts = shlex.split(self.command or "")
            if command_parts:
                validate_mcp_stdio_config(command_parts[0], command_parts[1:], None)
            self.tools = await self.client.connect_to_server(self.command)

        tool_list = []

        for tool in self.tools:
            args_schema = create_input_schema_from_json_schema(tool.inputSchema)
            tool_list.append(
                StructuredTool(
                    name=tool.name,
                    description=tool.description,
                    args_schema=args_schema,
                    func=create_tool_func(tool.name, args_schema, self.client.session),
                    coroutine=create_tool_coroutine(tool.name, args_schema, self.client.session),
                )
            )
        self.tool_names = [tool.name for tool in self.tools]
        return tool_list

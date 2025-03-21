import asyncio
import logging
import os
from contextlib import AsyncExitStack

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
from langflow.inputs import DropdownInput
from langflow.inputs.inputs import InputTypes
from langflow.io import MessageTextInput, Output, TabInput
from langflow.io.schema import schema_to_langflow_inputs
from langflow.schema import Message

# Define constant for status code
HTTP_TEMPORARY_REDIRECT = 307

logger = logging.getLogger(__name__)


class MCPStdioClient:
    def __init__(self):
        self.session: ClientSession | None = None
        self.exit_stack = AsyncExitStack()
        self.stdio = None
        self.write = None

    async def connect_to_server(self, command_str: str):
        try:
            command = command_str.split(" ")
            server_params = StdioServerParameters(
                command=command[0],
                args=command[1:],
                env={"DEBUG": "true", "PATH": os.environ["PATH"]},
            )

            # Use a new exit stack for this connection
            async with AsyncExitStack() as stack:
                stdio_transport = await stack.enter_async_context(stdio_client(server_params))
                self.stdio, self.write = stdio_transport
                self.session = await stack.enter_async_context(ClientSession(self.stdio, self.write))
                await self.session.initialize()
                response = await self.session.list_tools()

                # Transfer context to instance exit stack
                await stack.pop_all().aclose()
                return response.tools

        except Exception as e:
            msg = f"Error connecting to MCP server: {e}"
            raise ValueError(msg)


class MCPSseClient:
    def __init__(self):
        self.write = None
        self.sse = None
        self.session: ClientSession | None = None
        self.exit_stack = AsyncExitStack()

    async def _connect_with_timeout(
        self, url: str, headers: dict[str, str] | None, timeout_seconds: int, sse_read_timeout_seconds: int
    ):
        async with AsyncExitStack() as stack:
            sse_transport = await stack.enter_async_context(
                sse_client(url, headers, timeout_seconds, sse_read_timeout_seconds)
            )
            self.sse, self.write = sse_transport
            self.session = await stack.enter_async_context(ClientSession(self.sse, self.write))
            await self.session.initialize()
            await stack.pop_all().aclose()

    async def connect_to_server(
        self, url: str, headers: dict[str, str] | None, timeout_seconds: int = 500, sse_read_timeout_seconds: int = 500
    ):
        try:
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
        except Exception as e:
            msg = f"Error connecting to MCP server: {e}"
            raise ValueError(msg)


class MCPTools(Component):
    schema_inputs: list[InputTypes] = []
    stdio_client = MCPStdioClient()
    sse_client = MCPSseClient()
    tools = []  # Will hold the list of available tools
    tool_names = [str]

    display_name = "MCP Tools"
    description = (
        "Connects to an MCP server over Stdio or SSE and exposes its tools as Langflow tools to be used by an Agent."
    )
    icon = "code"
    name = "MCPTools"

    inputs = [
        TabInput(
            name="mode",
            display_name="Mode",
            options=["Stdio", "SSE"],
            value="Stdio",
            info="Select the connection mode",
            real_time_refresh=True,
        ),
        MessageTextInput(
            name="command",
            display_name="MCP Command",
            info="Command for MCP stdio connection",
            value="uvx mcp-sse-shim@latest",
            show=True,  # Shown when mode is Stdio
            # real_time_refresh=True,
            refresh_button=True,
        ),
        MessageTextInput(
            name="sse_url",
            display_name="MCP SSE URL",
            info="URL for MCP SSE connection",
            value="http://localhost:7860/api/v1/mcp/sse",
            show=False,  # Shown when mode is SSE
            # real_time_refresh=True,
            refresh_button=True,
        ),
        DropdownInput(
            name="tool",
            display_name="Tool",
            options=[],
            value="",
            info="Select the tool to execute",
            show=True,
            required=True,
            # real_time_refresh=True,
            refresh_button=True,
        ),
    ]

    outputs = [
        Output(display_name="Tools", name="tools", method="build_output"),
    ]

    async def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None) -> dict:
        """Toggle the visibility of connection-specific fields based on the selected mode."""
        if field_name == "mode":
            if field_value == "Stdio":
                build_config["command"]["show"] = True
                build_config["sse_url"]["show"] = False
            elif field_value == "SSE":
                build_config["command"]["show"] = False
                build_config["sse_url"]["show"] = True
        elif field_name == "command" or field_name == "sse_url":
            try:
                await self.update_tools()
                # Safely update the tool options after tools are updated
                if "tool" in build_config:
                    build_config["tool"]["options"] = self.tool_names
            except Exception as e:
                # Handle any errors during tool update
                build_config["tool"]["options"] = []
                msg = f"Failed to update tools: {e!s}"
                raise ValueError(msg)
        elif field_name == "tool":
            if len(self.tools) == 0:
                await self.update_tools()
            if self.tool is None:
                return build_config
            tool_obj = None
            for tool in self.tools:
                if tool.name == self.tool:
                    tool_obj = tool
                    break
            if tool_obj is None:
                logger.warning(f"Tool {self.tool} not found in available tools: {self.tools}")
                return build_config

            try:
                input_schema = create_input_schema_from_json_schema(tool_obj.inputSchema)
                self.schema_inputs = schema_to_langflow_inputs(input_schema)

                # Ensure schema_inputs is never None
                if self.schema_inputs is None:
                    self.schema_inputs = []

                for schema_input in self.schema_inputs:
                    name = schema_input.name
                    input_dict = schema_input.dict()
                    # Ensure required fields are present
                    if "value" not in input_dict:
                        input_dict["value"] = None
                    if "required" not in input_dict:
                        input_dict["required"] = True
                    build_config[name] = input_dict

            except Exception as e:
                logger.error(f"Error updating build config: {e!s}")
                # Return original build_config on error
                return build_config

        return build_config

    async def build_output(self) -> Message:
        # convert tool to DataFrame using args_schema
        await self.update_tools()
        if not self.tool:
            raise ValueError("No tool selected")
        kwargs = {}
        for schema_input in self.schema_inputs:
            kwargs[schema_input.name] = self.get(schema_input.name)
        output = await self.tool.func(kwargs)
        print(output)
        print(type(output))
        return Message(text=output)

    async def update_tools(self) -> list[StructuredTool]:
        """Connect to the MCP server using the selected mode and return available tools as StructuredTool instances."""
        if self.mode == "Stdio":
            if self.stdio_client.session is None:
                self.tools = await self.stdio_client.connect_to_server(self.command)
        elif self.mode == "SSE":
            if self.sse_client.session is None:
                self.tools = await self.sse_client.connect_to_server(self.sse_url, {})
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

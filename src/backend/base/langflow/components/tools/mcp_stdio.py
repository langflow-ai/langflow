# from langflow.field_typing import Data
import os
from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack
from typing import Any

from anthropic import Anthropic, BaseModel
from dotenv import load_dotenv
from langchain_core.tools import StructuredTool
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pydantic import Field, create_model

from langflow.custom import Component
from langflow.io import MessageTextInput, Output

load_dotenv()  # load environment variables from .env


class MCPClient:
    def __init__(self):
        # Initialize session and client objects
        self.session: ClientSession | None = None
        self.exit_stack = AsyncExitStack()
        self.anthropic = Anthropic()

    async def connect_to_server(self, command: str):
        server_params = StdioServerParameters(
            command="uvx", args=["mcp-sse-shim"], env={"DEBUG": "true", "PATH": os.environ["PATH"]}
        )

        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))

        await self.session.initialize()

        # List available tools
        response = await self.session.list_tools()
        tools = response.tools
        print("\nConnected to server with tools:", [tool.name for tool in tools])
        return tools


def create_input_schema_from_json_schema(schema: dict[str, Any]) -> type[BaseModel]:
    """Converts a JSON schema into a Pydantic model dynamically.

    :param schema: The JSON schema as a dictionary.
    :return: A Pydantic model class.
    """
    if schema.get("type") != "object":
        raise ValueError("JSON schema must be of type 'object' at the root level.")

    fields = {}
    properties = schema.get("properties", {})
    required_fields = set(schema.get("required", []))

    for field_name, field_def in properties.items():
        # Extract type
        field_type_str = field_def.get("type", "str")  # Default to string type if not specified
        field_type = {
            "string": str,
            "str": str,
            "integer": int,
            "int": int,
            "number": float,
            "boolean": bool,
            "array": list,
            "object": dict,
        }.get(field_type_str, Any)

        # Extract description and default if present
        field_metadata = {"description": field_def.get("description", "")}
        if field_name not in required_fields:
            field_metadata["default"] = field_def.get("default", None)

        # Create Pydantic field
        fields[field_name] = (field_type, Field(**field_metadata))

    # Dynamically create the model
    return create_model("InputSchema", **fields)


class MCPStdio(Component):
    client = MCPClient()
    tools = None
    tool_names = []
    display_name = "Get Tools from MCP"
    description = "Use as a template to create your own component."
    documentation: str = "http://docs.langflow.org/components/custom"
    icon = "code"
    name = "CustomComponent"

    inputs = [
        MessageTextInput(
            name="command",
            display_name="mcp command",
            info="mcp command",
            value="uv mcp-sse-shim@latest",
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(display_name="Output", name="output", method="build_output"),
    ]

    def create_tool_coroutine(self, tool_name: str) -> Callable[[dict], Awaitable]:
        async def tool_coroutine(*args, **kwargs):
            return await self.client.session.call_tool(tool_name, arguments=kwargs)

        return tool_coroutine

    async def build_output(self) -> list[StructuredTool]:
        if self.client.session is None:
            self.tools = await self.client.connect_to_server(self.command)

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

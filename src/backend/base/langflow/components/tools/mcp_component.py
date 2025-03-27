import asyncio
from typing import Any

from langchain_core.tools import StructuredTool

from langflow.base.mcp.util import (
    MCPSseClient,
    MCPStdioClient,
    create_input_schema_from_json_schema,
    create_tool_coroutine,
    create_tool_func,
)
from langflow.custom import Component
from langflow.inputs import DropdownInput
from langflow.inputs.inputs import InputTypes
from langflow.io import MessageTextInput, Output, TabInput
from langflow.io.schema import schema_to_langflow_inputs
from langflow.logging import logger
from langflow.schema import Message


class MCPToolsComponent(Component):
    schema_inputs: list[InputTypes] = []
    stdio_client = MCPStdioClient()
    sse_client = MCPSseClient()
    tools: list = []
    tool_names: list[str] = []
    _tool_cache: dict = {}  # Cache for tool objects
    default_keys = ["code", "_type", "mode", "command", "sse_url", "tool_placeholder", "tool_mode", "tool"]

    display_name = "MCP Server"
    description = "Connect to an MCP server and expose tools."
    icon = "server"
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
            value="uvx mcp-server-fetch",
            show=True,
            refresh_button=True,
        ),
        MessageTextInput(
            name="sse_url",
            display_name="MCP SSE URL",
            info="URL for MCP SSE connection",
            value="http://localhost:7860/api/v1/mcp/sse",
            show=False,
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
            real_time_refresh=True,
        ),
        MessageTextInput(
            name="tool_placeholder",
            display_name="Tool Placeholder",
            info="Placeholder for the tool",
            value="",
            show=False,
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(display_name="Response", name="response", method="build_output"),
    ]

    async def _validate_connection_params(self, mode: str, command: str | None = None, url: str | None = None) -> None:
        """Validate connection parameters based on mode."""
        if mode not in ["Stdio", "SSE"]:
            msg = f"Invalid mode: {mode}. Must be either 'Stdio' or 'SSE'"
            raise ValueError(msg)

        if mode == "Stdio" and not command:
            msg = "Command is required for Stdio mode"
            raise ValueError(msg)
        if mode == "SSE" and not url:
            msg = "URL is required for SSE mode"
            raise ValueError(msg)

    async def _validate_schema_inputs(self, tool_obj) -> list[InputTypes]:
        """Validate and process schema inputs for a tool."""
        try:
            if not tool_obj or not hasattr(tool_obj, "inputSchema"):
                msg = "Invalid tool object or missing input schema"
                raise ValueError(msg)

            input_schema = create_input_schema_from_json_schema(tool_obj.inputSchema)
            if not input_schema:
                msg = f"Empty input schema for tool '{tool_obj.name}'"
                raise ValueError(msg)

            schema_inputs = schema_to_langflow_inputs(input_schema)
            if not schema_inputs:
                msg = f"No input parameters defined for tool '{tool_obj.name}'"
                logger.warning(msg)
                return []

        except Exception as e:
            msg = f"Error validating schema inputs: {e!s}"
            logger.exception(msg)
            raise ValueError(msg) from e
        else:
            return schema_inputs

    async def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None) -> dict:
        """Toggle the visibility of connection-specific fields based on the selected mode."""
        try:
            if field_name == "mode":
                self.remove_non_default_keys(build_config)
                if field_value == "Stdio":
                    build_config["command"]["show"] = True
                    build_config["sse_url"]["show"] = False
                elif field_value == "SSE":
                    build_config["command"]["show"] = False
                    build_config["sse_url"]["show"] = True
            if field_name in ("command", "sse_url", "mode"):
                try:
                    await self.update_tools()
                    if "tool" in build_config:
                        build_config["tool"]["options"] = self.tool_names
                except Exception as e:
                    build_config["tool"]["options"] = []
                    msg = f"Failed to update tools: {e!s}"
                    raise ValueError(msg) from e
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
                    msg = f"Tool {self.tool} not found in available tools: {self.tools}"
                    logger.warning(msg)
                    return build_config
                self.remove_non_default_keys(build_config)
                await self._update_tool_config(build_config, field_value)
            elif field_name == "tool_mode":
                build_config["tool"]["show"] = not field_value
                for key, value in list(build_config.items()):
                    if key not in self.default_keys and isinstance(value, dict) and "show" in value:
                        build_config[key]["show"] = not field_value

        except Exception as e:
            msg = f"Error in update_build_config: {e!s}"
            logger.exception(msg)
            raise ValueError(msg) from e
        else:
            return build_config

    def get_inputs_for_all_tools(self, tools: list) -> dict:
        """Get input schemas for all tools."""
        inputs = {}
        for tool in tools:
            if not tool or not hasattr(tool, "name"):
                continue
            try:
                input_schema = schema_to_langflow_inputs(create_input_schema_from_json_schema(tool.inputSchema))
                inputs[tool.name] = input_schema
            except (AttributeError, ValueError, TypeError, KeyError) as e:
                msg = f"Error getting inputs for tool {getattr(tool, 'name', 'unknown')}: {e!s}"
                logger.exception(msg)
                continue
        return inputs

    def remove_input_schema_from_build_config(
        self, build_config: dict, tool_name: str, input_schema: dict[list[InputTypes], Any]
    ):
        """Remove the input schema for the tool from the build config."""
        # Keep only schemas that don't belong to the current tool
        input_schema = {k: v for k, v in input_schema.items() if k != tool_name}
        # Remove all inputs from other tools
        for value in input_schema.values():
            for _input in value:
                if _input.name in build_config:
                    build_config.pop(_input.name)

    def remove_non_default_keys(self, build_config: dict) -> None:
        """Remove non-default keys from the build config."""
        for key in list(build_config.keys()):
            if key not in self.default_keys:
                build_config.pop(key)

    async def _update_tool_config(self, build_config: dict, tool_name: str) -> None:
        """Update tool configuration with proper error handling."""
        if not self.tools:
            await self.update_tools()

        if not tool_name:
            return

        tool_obj = next((tool for tool in self.tools if tool.name == tool_name), None)
        if not tool_obj:
            msg = f"Tool {tool_name} not found in available tools: {self.tools}"
            logger.warning(msg)
            return

        try:
            # Get all tool inputs and remove old ones
            input_schema_for_all_tools = self.get_inputs_for_all_tools(self.tools)
            self.remove_input_schema_from_build_config(build_config, tool_name, input_schema_for_all_tools)

            # Get and validate new inputs
            self.schema_inputs = await self._validate_schema_inputs(tool_obj)
            if not self.schema_inputs:
                msg = f"No input parameters to configure for tool '{tool_name}'"
                logger.info(msg)
                return

            # Add new inputs to build config
            for schema_input in self.schema_inputs:
                if not schema_input or not hasattr(schema_input, "name"):
                    msg = "Invalid schema input detected, skipping"
                    logger.warning(msg)
                    continue

                try:
                    name = schema_input.name
                    input_dict = schema_input.to_dict()
                    input_dict.setdefault("value", None)
                    input_dict.setdefault("required", True)
                    build_config[name] = input_dict
                except (AttributeError, KeyError, TypeError) as e:
                    msg = f"Error processing schema input {schema_input}: {e!s}"
                    logger.exception(msg)
                    continue

        except ValueError as e:
            msg = f"Schema validation error for tool {tool_name}: {e!s}"
            logger.exception(msg)
            self.schema_inputs = []
            return
        except (AttributeError, KeyError, TypeError) as e:
            msg = f"Error updating tool config: {e!s}"
            logger.exception(msg)
            raise ValueError(msg) from e

    async def build_output(self) -> Message:
        """Build output with improved error handling and validation."""
        try:
            await self.update_tools()
            if self.tool != "":
                exec_tool = self._tool_cache[self.tool]
                tool_args = self.get_inputs_for_all_tools(self.tools)[self.tool]
                kwargs = {}
                for arg in tool_args:
                    value = getattr(self, arg.name, None)
                    if value:
                        kwargs[arg.name] = value
                output = await exec_tool.coroutine(**kwargs)
                return Message(text=output.content[len(output.content) - 1].text)
            return Message(text="You must select a tool", error=True)
        except Exception as e:
            msg = f"Error in build_output: {e!s}"
            logger.exception(msg)
            raise ValueError(msg) from e

    async def update_tools(self) -> list[StructuredTool]:
        """Connect to the MCP server and update available tools with improved error handling."""
        try:
            await self._validate_connection_params(self.mode, self.command, self.sse_url)

            if self.mode == "Stdio":
                if not self.stdio_client.session:
                    self.tools = await self.stdio_client.connect_to_server(self.command)
            elif self.mode == "SSE" and not self.sse_client.session:
                self.tools = await self.sse_client.connect_to_server(self.sse_url, {})

            if not self.tools:
                logger.warning("No tools returned from server")
                return []

            tool_list = []
            for tool in self.tools:
                if not tool or not hasattr(tool, "name"):
                    logger.warning("Invalid tool object detected, skipping")
                    continue

                try:
                    args_schema = create_input_schema_from_json_schema(tool.inputSchema)
                    if not args_schema:
                        msg = f"Empty schema for tool '{tool.name}', skipping"
                        logger.warning(msg)
                        continue

                    client = self.stdio_client if self.mode == "Stdio" else self.sse_client
                    if not client or not client.session:
                        msg = f"Invalid client session for tool '{tool.name}'"
                        raise ValueError(msg)

                    tool_obj = StructuredTool(
                        name=tool.name,
                        description=tool.description or "",
                        args_schema=args_schema,
                        func=create_tool_func(tool.name, args_schema, client.session),
                        coroutine=create_tool_coroutine(tool.name, args_schema, client.session),
                        tags=[tool.name],
                    )
                    tool_list.append(tool_obj)
                    self._tool_cache[tool.name] = tool_obj
                except (AttributeError, ValueError, TypeError, KeyError) as e:
                    msg = f"Error creating tool {getattr(tool, 'name', 'unknown')}: {e!s}"
                    logger.exception(msg)
                    continue

            self.tool_names = [tool.name for tool in self.tools if hasattr(tool, "name")]

        except (ValueError, RuntimeError, asyncio.TimeoutError) as e:
            msg = f"Error updating tools: {e!s}"
            logger.exception(msg)
            raise ValueError(msg) from e
        else:
            return tool_list

    async def _get_tools(self):
        """Get cached tools or update if necessary."""
        if not self.tools:
            return await self.update_tools()
        return self.tools

import re
import shutil
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
from langflow.io import McpInput, MessageTextInput, Output, DropdownInput  # Import McpInput from langflow.io
from langflow.io.schema import flatten_schema, schema_to_langflow_inputs
from langflow.services.auth.utils import create_user_longterm_token
from langflow.services.database.models.user.crud import get_user_by_id
from langflow.logging import logger
from langflow.schema import DataFrame
from langflow.inputs.inputs import InputTypes
from langflow.services.deps import get_session, get_settings_service, get_storage_service

# Import get_server from the backend API
from langflow.api.v2.mcp import get_server


def maybe_unflatten_dict(flat: dict[str, Any]) -> dict[str, Any]:
    """If any key looks nested (contains a dot or “[index]”), rebuild the.

    full nested structure; otherwise return flat as is.
    """
    # Quick check: do we have any nested keys?
    if not any(re.search(r"\.|\[\d+\]", key) for key in flat):
        return flat

    # Otherwise, unflatten into dicts/lists
    nested: dict[str, Any] = {}
    array_re = re.compile(r"^(.+)\[(\d+)\]$")

    for key, val in flat.items():
        parts = key.split(".")
        cur = nested
        for i, part in enumerate(parts):
            m = array_re.match(part)
            # Array segment?
            if m:
                name, idx = m.group(1), int(m.group(2))
                lst = cur.setdefault(name, [])
                # Ensure list is big enough
                while len(lst) <= idx:
                    lst.append({})
                if i == len(parts) - 1:
                    lst[idx] = val
                else:
                    cur = lst[idx]
            # Normal object key
            elif i == len(parts) - 1:
                cur[part] = val
            else:
                cur = cur.setdefault(part, {})

    return nested


class MCPToolsComponent(Component):
    schema_inputs: list = []
    stdio_client: MCPStdioClient = MCPStdioClient()
    sse_client: MCPSseClient = MCPSseClient()
    tools: list = []
    tool_names: list[str] = []
    _tool_cache: dict = {}
    default_keys: list[str] = [
        "code",
        "_type",
        "tool_mode",
        "tool_placeholder",
        "mcp_server",
        "tool",
    ]

    display_name = "MCP Connection"
    description = "Connect to an MCP server to use its tools."
    icon = "Mcp"
    name = "MCPTools"

    inputs = [
        McpInput(
            name="mcp_server",
            display_name="MCP Server",
            info="Select the MCP Server that will be used by this component",
            real_time_refresh=True,
        ),
        DropdownInput(
            name="tool",
            display_name="Tool",
            options=[],
            value="",
            info="Select the tool to execute",
            show=False,
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
        if mode == "Stdio" and command:
            self._validate_node_installation(command)
        if mode == "SSE" and not url:
            msg = "URL is required for SSE mode"
            raise ValueError(msg)

    def _validate_node_installation(self, command: str) -> str:
        """Validate the npx command."""
        if "npx" in command and not shutil.which("node"):
            msg = "Node.js is not installed. Please install Node.js to use npx commands."
            raise ValueError(msg)
        return command

    def _process_headers(self, headers: Any) -> dict:
        """Process the headers input into a valid dictionary.

        Args:
            headers: The headers to process, can be dict, str, or list
        Returns:
            Processed dictionary
        """
        if headers is None:
            return {}
        if isinstance(headers, dict):
            return headers
        if isinstance(headers, list):
            processed_headers = {}
            try:
                for item in headers:
                    if not self._is_valid_key_value_item(item):
                        continue
                    key = item["key"]
                    value = item["value"]
                    processed_headers[key] = value
            except (KeyError, TypeError, ValueError) as e:
                self.log(f"Failed to process headers list: {e}")
                return {}  # Return empty dictionary instead of None
            return processed_headers
        return {}

    def _is_valid_key_value_item(self, item: Any) -> bool:
        """Check if an item is a valid key-value dictionary."""
        return isinstance(item, dict) and "key" in item and "value" in item

    async def _validate_schema_inputs(self, tool_obj) -> list[InputTypes]:
        """Validate and process schema inputs for a tool."""
        try:
            if not tool_obj or not hasattr(tool_obj, "inputSchema"):
                msg = "Invalid tool object or missing input schema"
                raise ValueError(msg)

            flat_schema = flatten_schema(tool_obj.inputSchema)
            input_schema = create_input_schema_from_json_schema(flat_schema)
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
            if field_name == "tool":
                try:
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
                except Exception as e:
                    build_config["tool"]["options"] = []
                    msg = f"Failed to update tools: {e!s}"
                    raise ValueError(msg) from e
                else:
                    return build_config
            elif field_name == "mcp_server":
                await self.update_tools()
                if "tool" in build_config and len(self.tool_names) > 0:
                    build_config["tool"]["show"] = True
                    build_config["tool"]["options"] = self.tool_names
                elif "tool" in build_config and len(self.tool_names) == 0:
                    build_config["tool"]["show"] = False
                    build_config["tool"]["options"] = []
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
                flat_schema = flatten_schema(tool.inputSchema)
                input_schema = create_input_schema_from_json_schema(flat_schema)
                langflow_inputs = schema_to_langflow_inputs(input_schema)
                inputs[tool.name] = langflow_inputs
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

    async def build_output(self) -> DataFrame:
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

                unflattened_kwargs = maybe_unflatten_dict(kwargs)

                output = await exec_tool.coroutine(**unflattened_kwargs)

                tool_content = []
                for item in output.content:
                    item_dict = item.model_dump()
                    tool_content.append(item_dict)
                return DataFrame(data=tool_content)
            return DataFrame(data=[{"error": "You must select a tool"}])
        except Exception as e:
            msg = f"Error in build_output: {e!s}"
            logger.exception(msg)
            raise ValueError(msg) from e

    async def update_tools(self):
        """Fetch server config and update available tools."""
        server_name = getattr(self, "mcp_server", None)
        if not server_name:
            self.tools = []
            self.tool_names = []
            return []

        # Fetch server config from backend
        # Assume self.current_user and self.session are available (if not, raise error)
        async for db in get_session():
            user_id, _ = await create_user_longterm_token(db)
            current_user = await get_user_by_id(db, user_id)

            server_config = await get_server(
                server_name,
                current_user,
                db,
                storage_service=get_storage_service(),
                settings_service=get_settings_service(),
            )
            if not server_config:
                self.tools = []
                self.tool_names = []
                return []

            mode = (
                "Stdio"
                if "command" in server_config and "args" in server_config
                else "SSE"
                if "url" in server_config
                else None
            )
            command = server_config.get("command", "")
            url = server_config.get("url", "")
            headers = self._process_headers(server_config.get("headers", {}))
            await self._validate_connection_params(mode, command, url)

            # Determine connection type and parameters
            if mode == "Stdio":
                # Stdio connection
                args = server_config.get("args", [])
                env = server_config.get("env", {})
                full_command = " ".join([command] + args)
                if not self.stdio_client.session:
                    self.tools = await self.stdio_client.connect_to_server(full_command, env)
                client = self.stdio_client
            elif mode == "SSE":
                # SSE connection
                env = server_config.get("env", {})
                if not self.sse_client.session:
                    self.tools = await self.sse_client.connect_to_server(url, env, headers=headers)
                client = self.sse_client
            else:
                raise ValueError("Invalid MCP server configuration.")

            if not self.tools:
                logger.warning("No tools returned from server")
                self.tool_names = []
                return []

            tool_list = []
            for tool in self.tools:
                if not tool or not hasattr(tool, "name"):
                    logger.warning("Invalid tool object detected, skipping")
                    continue
                try:
                    args_schema = create_input_schema_from_json_schema(tool.inputSchema)
                    if not args_schema:
                        logger.warning(f"Empty schema for tool '{tool.name}', skipping")
                        continue
                    client = self.stdio_client if mode == "Stdio" else self.sse_client
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
                        metadata={},
                    )
                    tool_list.append(tool_obj)
                    self._tool_cache[tool.name] = tool_obj
                except (AttributeError, ValueError, TypeError, KeyError) as e:
                    msg = f"Error creating tool {getattr(tool, 'name', 'unknown')}: {e}"
                    logger.exception(msg)
                    continue
            self.tool_names = [tool.name for tool in self.tools if hasattr(tool, "name")]
            return tool_list
        return []

    async def _get_tools(self):
        """Get cached tools or update if necessary."""
        # if not self.tools:
        if not self.mcp_server:
            msg = "MCP Server is not set"
            raise ValueError(msg)
        return await self.update_tools()

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
from langflow.inputs import DropdownInput, TableInput
from langflow.inputs.inputs import DefaultPromptField, InputTypes
from langflow.io import MessageTextInput, MultilineInput, Output, TabInput
from langflow.io.schema import flatten_schema, schema_to_langflow_inputs
from langflow.logging import logger
from langflow.schema import DataFrame


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
    schema_inputs: list[InputTypes] = []
    stdio_client: MCPStdioClient = MCPStdioClient()
    sse_client: MCPSseClient = MCPSseClient()
    tools: list = []
    prompts: list = []
    tool_names: list[str] = []
    _tool_cache: dict = {}  # Cache for tool objects
    _prompt_cache: dict = {}  # Cache for prompts
    client = None  # Current active client
    default_keys: list[str] = [
        "code",
        "_type",
        "mode",
        "command",
        "env",
        "sse_url",
        "tool_placeholder",
        "tool_mode",
        "tool",
        "prompt",
        "headers_input",
    ]

    display_name = "MCP Connection"
    description = "Connect to an MCP server to use its tools."
    icon = "Mcp"
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
            name="env",
            display_name="Env",
            info="Env vars to include in mcp stdio connection (i.e. DEBUG=true)",
            value="",
            is_list=True,
            show=True,
            tool_mode=False,
            advanced=True,
        ),
        MultilineInput(
            name="sse_url",
            display_name="MCP SSE URL",
            info="URL for MCP SSE connection",
            show=False,
            refresh_button=True,
            value="MCP_SSE",
            real_time_refresh=True,
        ),
        TableInput(
            name="headers_input",
            display_name="Headers",
            info="Headers to include in the tool",
            show=False,
            real_time_refresh=True,
            table_schema=[
                {
                    "name": "key",
                    "display_name": "Header",
                    "type": "str",
                    "description": "Header name",
                },
                {
                    "name": "value",
                    "display_name": "Value",
                    "type": "str",
                    "description": "Header value",
                },
            ],
            value=[],
            advanced=True,
        ),
        DropdownInput(
            name="prompt",
            display_name="Prompt",
            options=[],
            value="",
            info="Select the prompt to execute",
            show=True,
            required=False,
            real_time_refresh=True,
        ),
        DropdownInput(
            name="tool",
            display_name="Tool",
            options=[],
            value="",
            info="Select the tool to execute",
            show=True,
            required=False,
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
        Output(display_name="Tools", name="tools", method="build_tool_output"),
        Output(display_name="Prompts", name="prompts", method="build_prompt_output"),
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
            if field_name == "mode":
                # Mode-specific field visibility
                if field_value == "Stdio":
                    build_config["command"]["show"] = True
                    build_config["env"]["show"] = True
                    build_config["sse_url"]["show"] = False
                    build_config["headers_input"]["show"] = False
                elif field_value == "SSE":
                    build_config["command"]["show"] = False
                    build_config["env"]["show"] = False
                    build_config["sse_url"]["show"] = True
                    build_config["headers_input"]["show"] = True
                else:
                    msg = f"Invalid mode: {field_value}"
                    logger.error(msg)
                    raise ValueError(msg)

                # Reset and update tools and prompts
                self.tools = []
                self.prompts = []
                self.tool_names = []
                self._tool_cache = {}
                self._prompt_cache = {}
                await self.update_tools_and_prompts(
                    mode=field_value,
                    command=build_config["command"]["value"],
                    url=build_config["sse_url"]["value"],
                    env=build_config["env"]["value"],
                    headers=build_config["headers_input"]["value"],
                )

                # Update tool and prompt options
                build_config["tool"]["options"] = self.tool_names
                build_config["prompt"]["options"] = list(self.prompts)

            if field_name in ["command", "sse_url", "env", "headers_input"]:
                # Update tools and prompts when connection params change
                await self.update_tools_and_prompts(
                    mode=build_config["mode"]["value"],
                    command=build_config["command"]["value"],
                    url=build_config["sse_url"]["value"],
                    env=build_config["env"]["value"],
                    headers=build_config["headers_input"]["value"],
                )
                build_config["tool"]["options"] = self.tool_names
                build_config["prompt"]["options"] = list(self.prompts)

            if field_name == "prompt":
                if len(self.prompts) == 0:
                    await self.update_tools_and_prompts(
                        mode=build_config["mode"]["value"],
                        command=build_config["command"]["value"],
                        url=build_config["sse_url"]["value"],
                        env=build_config["env"]["value"],
                        headers=build_config["headers_input"]["value"],
                    )

                # Remove any existing prompt variables
                keys_to_remove = [k for k in build_config if k.startswith("prompt_var_")]
                for key in keys_to_remove:
                    del build_config[key]

                if field_value:
                    self.prompt = field_value

                    # Get prompt object and extract variables
                    prompt_obj = self._prompt_cache.get(field_value)
                    if not prompt_obj:
                        return build_config

                    # Extract variables from the prompt arguments
                    variables = []
                    if hasattr(prompt_obj, "arguments") and prompt_obj.arguments:
                        # Handle both string arguments and object arguments
                        for arg in prompt_obj.arguments:
                            if isinstance(arg, str):
                                variables.append(arg)
                            elif hasattr(arg, "name"):
                                variables.append(arg.name)

                    if not variables and hasattr(prompt_obj, "description") and prompt_obj.description:
                        variables = re.findall(r"\{(.*?)\}", prompt_obj.description)

                    if not variables:
                        return build_config

                    # Create a new ordered dictionary with prompt variables in the right position
                    new_build_config = {}

                    # Find the position of the prompt field
                    keys = list(build_config.keys())

                    # Insert prompt variables after the prompt field
                    prompt_index = keys.index("prompt") if "prompt" in keys else -1

                    if prompt_index >= 0:
                        # Add all keys up to and including prompt
                        for i in range(prompt_index + 1):
                            key = keys[i]
                            new_build_config[key] = build_config[key]

                        # Add prompt variables
                        for variable in variables:
                            if variable in ["chat_history", "agent_scratchpad"]:
                                continue

                            field_name = f"prompt_var_{variable}"
                            new_build_config[field_name] = DefaultPromptField(
                                name=field_name,
                                display_name="Prompt: " + variable,
                                info=f"Value for {{{variable}}} in the prompt",
                                advanced=False,
                                multiline=True,
                            ).to_dict()

                        # Add remaining keys
                        for i in range(prompt_index + 1, len(keys)):
                            key = keys[i]
                            new_build_config[key] = build_config[key]

                        # Replace build_config with new ordered version
                        build_config.clear()
                        build_config.update(new_build_config)

            elif field_name == "tool":
                if field_value:
                    self.tool = field_value
                    self.remove_non_default_keys(build_config)
                    await self._update_tool_config(build_config, field_value)

            # always return build_config
            return build_config  # noqa: TRY300
        except Exception as e:
            msg = f"Error in update_build_config: {e!s}"
            logger.exception(msg)
            raise ValueError(msg) from e

    # TODO: this bit doesn't work yet because of a bug
    def update_outputs(self, frontend_node: dict, field_name: str, field_value: Any) -> dict:
        for key in frontend_node["template"]:
            if key not in frontend_node["field_order"] and key != "code" and key != "_type":
                frontend_node["field_order"].append(key)
        return frontend_node

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
        keys_to_remove = [
            key for key in build_config if key not in self.default_keys and not key.startswith("prompt_var_")
        ]

        for key in keys_to_remove:
            build_config.pop(key)

    async def _update_tool_config(self, build_config: dict, tool_name: str) -> None:
        """Update tool configuration with proper error handling."""
        if not self.tools:
            await self.update_tools_and_prompts(
                mode=build_config["mode"]["value"],
                command=build_config["command"]["value"],
                url=build_config["sse_url"]["value"],
                env=build_config["env"]["value"],
                headers=build_config["headers_input"]["value"],
            )

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
                    # Prefix the input name with tool_var_ to avoid conflicts
                    original_name = schema_input.name
                    schema_input.name = f"tool_var_{original_name}"

                    # Also update the display name to indicate it's a tool variable
                    if hasattr(schema_input, "display_name"):
                        schema_input.display_name = f"Tool: {schema_input.display_name}"
                    else:
                        schema_input.display_name = f"Tool: {original_name}"

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

    async def build_prompt_output(self) -> DataFrame:
        try:
            await self.update_tools_and_prompts()
            if self.prompt and self.prompt != "":
                # Collect prompt variables from attributes
                prompt_kwargs = {}

                # Get all attributes from self._attributes that start with prompt_var_
                for attr_name, value in self._attributes.items():
                    if attr_name.startswith("prompt_var_"):
                        var_name = attr_name.replace("prompt_var_", "")
                        if value:  # Only add non-empty values
                            prompt_kwargs[var_name] = value

                result = await self.client.session.get_prompt(self.prompt, prompt_kwargs)
                # Convert to dataframe
                prompt_content = []
                for item in result.messages:
                    item_dict = item.model_dump()
                    prompt_content.append(item_dict)
                return DataFrame(data=prompt_content)
            return DataFrame(data=[{"error": "You must select a prompt"}])
        except Exception as e:  # noqa: BLE001
            return DataFrame(data=[{"error": f"Error fetching prompt output: {e!s}"}])

    async def build_tool_output(self) -> DataFrame:
        """Build output with improved error handling and validation."""
        try:
            await self.update_tools_and_prompts()
            if self.tool != "":
                exec_tool = self._tool_cache[self.tool]
                tool_args = self.get_inputs_for_all_tools(self.tools)[self.tool]
                kwargs = {}
                for arg in tool_args:
                    # Get the prefixed attribute name
                    prefixed_name = f"tool_var_{arg.name}"
                    # Get the value from the prefixed attribute
                    value = getattr(self, prefixed_name, None)
                    if value:
                        # Use the original name as the key in kwargs
                        kwargs[arg.name] = value

                unflattened_kwargs = maybe_unflatten_dict(kwargs)

                output = await exec_tool.coroutine(**unflattened_kwargs)

                tool_content = []
                for item in output.content:
                    item_dict = item.model_dump()
                    tool_content.append(item_dict)
                return DataFrame(data=tool_content)
            return DataFrame(data=[{"error": "You must select a tool"}])
        except Exception as e:  # noqa: BLE001
            return DataFrame(data=[{"error": f"Error fetching tool output: {e!s}"}])

    async def update_tools_and_prompts(
        self,
        mode: str | None = None,
        command: str | None = None,
        url: str | None = None,
        env: list[str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> list[StructuredTool]:
        """Connect to the MCP server and update available tools with improved error handling."""
        try:
            if mode is None:
                mode = self.mode
            if command is None:
                command = self.command
            if env is None:
                env = self.env
            if url is None:
                url = self.sse_url
            if headers is None:
                headers = self.headers_input
            headers = self._process_headers(headers)
            await self._validate_connection_params(mode, command, url)

            if mode == "Stdio":
                if not self.stdio_client.session:
                    try:
                        self.tools = await self.stdio_client.connect_to_server(command, env)
                    except ValueError as e:
                        msg = f"Error connecting to MCP server: {e}"
                        logger.exception(msg)
                        raise ValueError(msg) from e
                client = self.stdio_client
            elif mode == "SSE":
                if not self.sse_client.session:
                    try:
                        self.tools = await self.sse_client.connect_to_server(url, headers)
                    except ValueError as e:
                        logger.error(f"SSE URL validation error: {e}")
                        msg = f"Invalid SSE URL configuration: {e}. Please check your SSE URL and port."
                        raise ValueError(msg) from e
                    except ConnectionError as e:
                        logger.error(f"SSE connection error: {e}")
                        msg = (
                            f"Could not connect to SSE endpoint: {e}. "
                            "Please verify:\n"
                            "1. your sse mcp server is running\n"
                            "2. The SSE URL and port are correct\n"
                            "3. There are no network issues preventing the connection"
                        )
                        raise ValueError(msg) from e
                    except Exception as e:
                        logger.error(f"Unexpected SSE error: {e}")
                        msg = f"Unexpected error connecting to SSE endpoint: {e}"
                        raise ValueError(msg) from e
                client = self.sse_client
            else:
                logger.warning("Unknown mode, cannot fetch tools or prompts")
                return []

            # Set the current active client
            self.client = client

            # Fetch prompts if supported
            self.prompts = []
            if hasattr(client, "session") and client.session and hasattr(client.session, "list_prompts"):
                try:
                    response = await client.session.list_prompts()
                    prompt_list = response.prompts
                    prompts = []
                    for prompt in prompt_list:
                        prompts.append(prompt.name)
                        self._prompt_cache[prompt.name] = prompt
                    self.prompts = prompts
                except Exception as e:  # noqa: BLE001
                    logger.warning(f"Could not fetch prompts: {e}")

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
                        logger.warning(f"Empty schema for tool '{tool.name}', skipping")
                        continue

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

        except ValueError as e:
            raise ValueError(str(e)) from e
        except Exception as e:
            logger.exception("Error updating tools")
            msg = f"Failed to update tools: {e!s}"
            raise ValueError(msg) from e
        else:
            return tool_list

    async def _get_tools(self):
        """Get cached tools or update if necessary."""
        # if not self.tools:
        if self.mode == "SSE" and self.sse_url is None:
            msg = "SSE URL is not set"
            raise ValueError(msg)
        return await self.update_tools_and_prompts()

    async def _update_prompt_config(self, build_config: dict, prompt_name: str) -> None:
        """Update prompt configuration with dynamic input fields for prompt variables."""
        # Early return if prompt_name is empty or None
        if not prompt_name:
            return

        try:
            # First, ensure we have prompts loaded
            if not self.prompts:
                await self.update_tools_and_prompts(
                    mode=build_config["mode"]["value"],
                    command=build_config["command"]["value"],
                    url=build_config["sse_url"]["value"],
                    env=build_config["env"]["value"],
                    headers=build_config["headers_input"]["value"],
                )

            # Check if prompt exists in cache
            if prompt_name not in self._prompt_cache:
                msg = f"Prompt {prompt_name} not found in available prompts"
                return

            # Remove old prompt inputs
            self.remove_non_default_keys(build_config)

            # Get prompt template and extract variables
            prompt_obj = self._prompt_cache[prompt_name]

            # Extract variables from the prompt arguments
            variables = []
            if hasattr(prompt_obj, "arguments") and prompt_obj.arguments:
                variables = [arg.name for arg in prompt_obj.arguments if hasattr(arg, "name")]

            if not variables and hasattr(prompt_obj, "description") and prompt_obj.description:
                variables = re.findall(r"\{(.*?)\}", prompt_obj.description)

            if not variables:
                msg = f"No variables found for prompt '{prompt_name}'"
                return

            # Create a new ordered dictionary for the build config
            new_build_config = {}

            # Find the position of the prompt field
            prompt_position = -1
            for i, (key, _) in enumerate(build_config.items()):
                if key == "prompt":
                    prompt_position = i
                    break

            # Add all fields up to and including the prompt field
            keys = list(build_config.keys())
            for i in range(prompt_position + 1):
                if i < len(keys):
                    key = keys[i]
                    new_build_config[key] = build_config[key]

            # Add the prompt variable fields
            for variable in variables:
                # Skip internal variables or reserved names
                if variable in ["chat_history", "agent_scratchpad"]:
                    continue

                field_name = f"prompt_var_{variable}"
                new_build_config[field_name] = DefaultPromptField(
                    name=field_name,
                    display_name=variable,
                    info=f"Value for {{{variable}}} in the prompt",
                    advanced=False,
                    multiline=True,
                ).to_dict()

            # Add the remaining fields
            for i in range(prompt_position + 1, len(keys)):
                key = keys[i]
                new_build_config[key] = build_config[key]

            # Update the build_config with our new ordered version
            build_config.clear()
            build_config.update(new_build_config)

        except Exception as e:
            raise ValueError(msg) from e

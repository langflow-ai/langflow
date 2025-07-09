import asyncio
import re
import uuid
from typing import Any

from langchain_core.tools import StructuredTool

from langflow.api.v2.mcp import get_server
from langflow.base.mcp.util import (
    MCPSseClient,
    MCPStdioClient,
    create_input_schema_from_json_schema,
    update_tools,
)
from langflow.custom.custom_component.component_with_cache import ComponentWithCache
from langflow.inputs.inputs import InputTypes
from langflow.io import DropdownInput, McpInput, MessageTextInput, Output
from langflow.io.schema import flatten_schema, schema_to_langflow_inputs
from langflow.logging import logger
from langflow.schema.dataframe import DataFrame
from langflow.schema.message import Message
from langflow.services.auth.utils import create_user_longterm_token

# Import get_server from the backend API
from langflow.services.database.models.user.crud import get_user_by_id
from langflow.services.deps import get_session, get_settings_service, get_storage_service


def maybe_unflatten_dict(flat: dict[str, Any]) -> dict[str, Any]:
    """If any key looks nested (contains a dot or "[index]"), rebuild the.

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


class MCPToolsComponent(ComponentWithCache):
    schema_inputs: list = []
    tools: list[StructuredTool] = []
    _not_load_actions: bool = False
    _tool_cache: dict = {}
    _last_selected_server: str | None = None  # Cache for the last selected server

    def __init__(self, **data) -> None:
        super().__init__(**data)
        # Initialize cache keys to avoid CacheMiss when accessing them
        if "servers" not in self._shared_component_cache:
            self._shared_component_cache["servers"] = {}
        if "last_selected_server" not in self._shared_component_cache:
            self._shared_component_cache["last_selected_server"] = ""

        # Initialize clients with access to the component cache
        self.stdio_client: MCPStdioClient = MCPStdioClient(component_cache=self._shared_component_cache)
        self.sse_client: MCPSseClient = MCPSseClient(component_cache=self._shared_component_cache)

    default_keys: list[str] = [
        "code",
        "_type",
        "tool_mode",
        "tool_placeholder",
        "mcp_server",
        "tool",
    ]

    display_name = "MCP Tools"
    description = "Connect to an MCP server to use its tools."
    documentation: str = "https://docs.langflow.org/mcp-client"
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
            tool_mode=False,
        ),
    ]

    outputs = [
        Output(display_name="Response", name="response", method="build_output"),
    ]

    async def _validate_schema_inputs(self, tool_obj) -> list[InputTypes]:
        """Validate and process schema inputs for a tool."""
        try:
            if not tool_obj or not hasattr(tool_obj, "args_schema"):
                msg = "Invalid tool object or missing input schema"
                raise ValueError(msg)

            flat_schema = flatten_schema(tool_obj.args_schema.schema())
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

    async def update_tool_list(self, mcp_server_value=None):
        # Accepts mcp_server_value as dict {name, config} or uses self.mcp_server
        mcp_server = mcp_server_value if mcp_server_value is not None else getattr(self, "mcp_server", None)
        server_name = None
        server_config_from_value = None
        if isinstance(mcp_server, dict):
            server_name = mcp_server.get("name")
            server_config_from_value = mcp_server.get("config")
        else:
            server_name = mcp_server
        if not server_name:
            self.tools = []
            return [], {"name": server_name, "config": server_config_from_value}

        # Use shared cache if available
        cached = self._shared_component_cache["servers"].get(server_name)
        if cached is not None:
            self.tools = cached["tools"]
            self.tool_names = cached["tool_names"]
            self._tool_cache = cached["tool_cache"]
            server_config_from_value = cached["config"]
            return self.tools, {"name": server_name, "config": server_config_from_value}

        try:
            async for db in get_session():
                user_id, _ = await create_user_longterm_token(db)
                current_user = await get_user_by_id(db, user_id)

                # Try to get server config from DB/API
                server_config = await get_server(
                    server_name,
                    current_user,
                    db,
                    storage_service=get_storage_service(),
                    settings_service=get_settings_service(),
                )

                # If get_server returns empty but we have a config, use it
                if not server_config and server_config_from_value:
                    server_config = server_config_from_value

                if not server_config:
                    self.tools = []
                    return [], {"name": server_name, "config": server_config}

                _, tool_list, tool_cache = await update_tools(
                    server_name=server_name,
                    server_config=server_config,
                    mcp_stdio_client=self.stdio_client,
                    mcp_sse_client=self.sse_client,
                )

                self.tool_names = [tool.name for tool in tool_list if hasattr(tool, "name")]
                self._tool_cache = tool_cache
                self.tools = tool_list
                # Cache the result using shared cache

                self._shared_component_cache["servers"][server_name] = {
                    "tools": tool_list,
                    "tool_names": self.tool_names,
                    "tool_cache": tool_cache,
                    "config": server_config,
                }
                return tool_list, {"name": server_name, "config": server_config}
        except (TimeoutError, asyncio.TimeoutError) as e:
            msg = f"Timeout updating tool list: {e!s}"
            logger.exception(msg)
            raise TimeoutError(msg) from e
        except Exception as e:
            msg = f"Error updating tool list: {e!s}"
            logger.exception(msg)
            raise ValueError(msg) from e

    async def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None) -> dict:
        """Toggle the visibility of connection-specific fields based on the selected mode."""
        try:
            if field_name == "tool":
                try:
                    if len(self.tools) == 0:
                        try:
                            self.tools, build_config["mcp_server"]["value"] = await self.update_tool_list()
                            build_config["tool"]["options"] = [tool.name for tool in self.tools]
                            build_config["tool"]["placeholder"] = "Select a tool"
                        except (TimeoutError, asyncio.TimeoutError) as e:
                            msg = f"Timeout updating tool list: {e!s}"
                            logger.exception(msg)
                            if not build_config["tools_metadata"]["show"]:
                                build_config["tool"]["show"] = True
                                build_config["tool"]["options"] = []
                                build_config["tool"]["value"] = ""
                                build_config["tool"]["placeholder"] = "Timeout on MCP server"
                            else:
                                build_config["tool"]["show"] = False
                        except ValueError:
                            if not build_config["tools_metadata"]["show"]:
                                build_config["tool"]["show"] = True
                                build_config["tool"]["options"] = []
                                build_config["tool"]["value"] = ""
                                build_config["tool"]["placeholder"] = "Error on MCP Server"
                            else:
                                build_config["tool"]["show"] = False

                    if field_value == "":
                        return build_config
                    tool_obj = None
                    for tool in self.tools:
                        if tool.name == field_value:
                            tool_obj = tool
                            break
                    if tool_obj is None:
                        msg = f"Tool {field_value} not found in available tools: {self.tools}"
                        logger.warning(msg)
                        return build_config
                    await self._update_tool_config(build_config, field_value)
                except Exception as e:
                    build_config["tool"]["options"] = []
                    msg = f"Failed to update tools: {e!s}"
                    raise ValueError(msg) from e
                else:
                    return build_config
            elif field_name == "mcp_server":
                if not field_value:
                    build_config["tool"]["show"] = False
                    build_config["tool"]["options"] = []
                    build_config["tool"]["value"] = ""
                    build_config["tool"]["placeholder"] = ""
                    build_config["tool_placeholder"]["tool_mode"] = False
                    self.remove_non_default_keys(build_config)
                    return build_config

                build_config["tool_placeholder"]["tool_mode"] = True

                current_server_name = field_value.get("name") if isinstance(field_value, dict) else field_value
                _last_selected_server = self._shared_component_cache.get("last_selected_server") or ""

                # To avoid unnecessary updates, only proceed if the server has actually changed
                if (_last_selected_server in (current_server_name, "")) and build_config["tool"]["show"]:
                    return build_config

                # Determine if "Tool Mode" is active by checking if the tool dropdown is hidden.
                is_in_tool_mode = build_config["tools_metadata"]["show"]
                self._shared_component_cache.set("last_selected_server", current_server_name)

                # Check if tools are already cached for this server before clearing
                cached_tools = None
                if current_server_name:
                    cached = self._shared_component_cache["servers"].get(current_server_name)
                    if cached is not None:
                        cached_tools = cached["tools"]
                        self.tools = cached_tools
                        self.tool_names = cached["tool_names"]
                        self._tool_cache = cached["tool_cache"]

                # Only clear tools if we don't have cached tools for the current server
                if not cached_tools:
                    self.tools = []  # Clear previous tools only if no cache

                self.remove_non_default_keys(build_config)  # Clear previous tool inputs

                # Only show the tool dropdown if not in tool_mode
                if not is_in_tool_mode:
                    build_config["tool"]["show"] = True
                    if cached_tools:
                        # Use cached tools to populate options immediately
                        build_config["tool"]["options"] = [tool.name for tool in cached_tools]
                        build_config["tool"]["placeholder"] = "Select a tool"
                    else:
                        # Show loading state only when we need to fetch tools
                        build_config["tool"]["placeholder"] = "Loading tools..."
                        build_config["tool"]["options"] = []
                    build_config["tool"]["value"] = uuid.uuid4()
                else:
                    # Keep the tool dropdown hidden if in tool_mode
                    self._not_load_actions = True
                    build_config["tool"]["show"] = False

            elif field_name == "tool_mode":
                build_config["tool"]["placeholder"] = ""
                build_config["tool"]["show"] = not bool(field_value) and bool(build_config["mcp_server"])
                self.remove_non_default_keys(build_config)
                self.tool = build_config["tool"]["value"]
                if field_value:
                    self._not_load_actions = True
                else:
                    build_config["tool"]["value"] = uuid.uuid4()
                    build_config["tool"]["options"] = []
                    build_config["tool"]["show"] = True
                    build_config["tool"]["placeholder"] = "Loading tools..."
            elif field_name == "tools_metadata":
                self._not_load_actions = False

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
                flat_schema = flatten_schema(tool.args_schema.schema())
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
            self.tools, build_config["mcp_server"]["value"] = await self.update_tool_list()

        if not tool_name:
            return

        tool_obj = next((tool for tool in self.tools if tool.name == tool_name), None)
        if not tool_obj:
            msg = f"Tool {tool_name} not found in available tools: {self.tools}"
            self.remove_non_default_keys(build_config)
            build_config["tool"]["value"] = ""
            logger.warning(msg)
            return

        try:
            # Store current values before removing inputs
            current_values = {}
            for key, value in build_config.items():
                if key not in self.default_keys and isinstance(value, dict) and "value" in value:
                    current_values[key] = value["value"]

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

                    # Preserve existing value if the parameter name exists in current_values
                    if name in current_values:
                        build_config[name]["value"] = current_values[name]

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
            self.tools, _ = await self.update_tool_list()
            if self.tool != "":
                # Set session context for persistent MCP sessions using Langflow session ID
                session_context = self._get_session_context()
                if session_context:
                    self.stdio_client.set_session_context(session_context)
                    self.sse_client.set_session_context(session_context)

                exec_tool = self._tool_cache[self.tool]
                tool_args = self.get_inputs_for_all_tools(self.tools)[self.tool]
                kwargs = {}
                for arg in tool_args:
                    value = getattr(self, arg.name, None)
                    if value:
                        if isinstance(value, Message):
                            kwargs[arg.name] = value.text
                        else:
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

    def _get_session_context(self) -> str | None:
        """Get the Langflow session ID for MCP session caching."""
        # Try to get session ID from the component's execution context
        if hasattr(self, "graph") and hasattr(self.graph, "session_id"):
            session_id = self.graph.session_id
            # Include server name to ensure different servers get different sessions
            server_name = ""
            mcp_server = getattr(self, "mcp_server", None)
            if isinstance(mcp_server, dict):
                server_name = mcp_server.get("name", "")
            elif mcp_server:
                server_name = str(mcp_server)
            return f"{session_id}_{server_name}" if session_id else None
        return None

    async def _get_tools(self):
        """Get cached tools or update if necessary."""
        mcp_server = getattr(self, "mcp_server", None)
        if not self._not_load_actions:
            tools, _ = await self.update_tool_list(mcp_server)
            return tools
        return []

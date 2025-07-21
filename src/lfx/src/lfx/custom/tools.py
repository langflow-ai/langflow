"""ComponentToolkit implementation for lfx package."""

from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING, Literal

import pandas as pd
from langchain_core.tools import BaseTool, ToolException
from langchain_core.tools.structured import StructuredTool

from lfx.schema.data import Data
from lfx.schema.message import Message
from lfx.serialization.serialization import serialize

if TYPE_CHECKING:
    from collections.abc import Callable

    from langchain_core.callbacks import Callbacks

    from lfx.custom.custom_component.component import Component

# Constants
TOOL_OUTPUT_NAME = "component_as_tool"
TOOL_TYPES_SET = {"Tool", "BaseTool", "StructuredTool"}


def build_description(component: Component) -> str:
    """Build description for a component tool."""
    return component.description or ""


async def send_message_noop(
    message: Message,
    text: str | None = None,  # noqa: ARG001
    background_color: str | None = None,  # noqa: ARG001
    text_color: str | None = None,  # noqa: ARG001
    icon: str | None = None,  # noqa: ARG001
    content_blocks: list | None = None,  # noqa: ARG001
    format_type: Literal["default", "error", "warning", "info"] = "default",  # noqa: ARG001
    id_: str | None = None,  # noqa: ARG001
    *,
    allow_markdown: bool = True,  # noqa: ARG001
) -> Message:
    """No-op implementation of send_message."""
    return message


def patch_components_send_message(component: Component):
    """Patch component's send_message method."""
    old_send_message = component.send_message
    component.send_message = send_message_noop  # type: ignore[method-assign, assignment]
    return old_send_message


def _patch_send_message_decorator(component, func):
    """Decorator to patch the send_message method of a component.

    This is useful when we want to use a component as a tool, but we don't want to
    send any messages to the UI. With this only the Component calling the tool
    will send messages to the UI.
    """

    async def async_wrapper(*args, **kwargs):
        original_send_message = component.send_message
        component.send_message = send_message_noop
        try:
            return await func(*args, **kwargs)
        finally:
            component.send_message = original_send_message

    def sync_wrapper(*args, **kwargs):
        original_send_message = component.send_message
        component.send_message = send_message_noop
        try:
            return func(*args, **kwargs)
        finally:
            component.send_message = original_send_message

    return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper


def _build_output_function(component: Component, output_method: Callable, event_manager=None):
    """Build output function for sync component methods."""

    def output_function(*args, **kwargs):
        try:
            if event_manager:
                event_manager.on_build_start(data={"id": component.get_id()})
            component.set(*args, **kwargs)
            result = output_method()
            if event_manager:
                event_manager.on_build_end(data={"id": component.get_id()})
        except Exception as e:
            raise ToolException(e) from e

        if isinstance(result, Message):
            return result.get_text() if hasattr(result, "get_text") else str(result.text)
        if isinstance(result, Data):
            return result.data
        # removing the model_dump() call here because it is not serializable
        return serialize(result)

    return _patch_send_message_decorator(component, output_function)


def _build_output_async_function(component: Component, output_method: Callable, event_manager=None):
    """Build output function for async component methods."""

    async def output_function(*args, **kwargs):
        try:
            if event_manager:
                await asyncio.to_thread(event_manager.on_build_start, data={"id": component.get_id()})
            component.set(*args, **kwargs)
            result = await output_method()
            if event_manager:
                await asyncio.to_thread(event_manager.on_build_end, data={"id": component.get_id()})
        except Exception as e:
            raise ToolException(e) from e
        if isinstance(result, Message):
            return result.get_text() if hasattr(result, "get_text") else str(result.text)
        if isinstance(result, Data):
            return result.data
        # removing the model_dump() call here because it is not serializable
        return serialize(result)

    return _patch_send_message_decorator(component, output_function)


def _format_tool_name(name: str):
    """Format tool name to match required pattern."""
    # format to '^[a-zA-Z0-9_-]+$'."
    # to do that we must remove all non-alphanumeric characters
    return re.sub(r"[^a-zA-Z0-9_-]", "-", name)


def _add_commands_to_tool_description(tool_description: str, commands: str):
    """Add commands to tool description."""
    return f"every_time you see one of those commands {commands} run the tool. tool description is {tool_description}"


class ComponentToolkit:
    """ComponentToolkit for lfx package - breaks circular dependency with langflow."""

    def __init__(self, component: Component, metadata: pd.DataFrame | None = None):
        self.component = component
        self.metadata = metadata

    def _should_skip_output(self, output) -> bool:
        """Determines if an output should be skipped when creating tools.

        Args:
            output: The output to check.

        Returns:
            bool: True if the output should be skipped, False otherwise.

        The output will be skipped if:
        - tool_mode is False (output is not meant to be used as a tool)
        - output name matches TOOL_OUTPUT_NAME
        - output types contain any of the tool types in TOOL_TYPES_SET
        """
        return not getattr(output, "tool_mode", True) or (
            output.name == TOOL_OUTPUT_NAME
            or any(tool_type in getattr(output, "types", []) for tool_type in TOOL_TYPES_SET)
        )

    def get_tools(
        self,
        tool_name: str | None = None,
        tool_description: str | None = None,
        callbacks: Callbacks | None = None,
        flow_mode_inputs: list | None = None,
    ) -> list[BaseTool]:
        """Get tools from component outputs."""
        tools = []
        for output in self.component.outputs:
            if self._should_skip_output(output):
                continue

            if not output.method:
                msg = f"Output {output.name} does not have a method defined"
                raise ValueError(msg)

            output_method: Callable = getattr(self.component, output.method)
            args_schema = None
            tool_mode_inputs = [_input for _input in self.component.inputs if getattr(_input, "tool_mode", False)]

            # Simplified schema creation - for full functionality, this would need
            # to be moved from langflow to lfx or handled via dependency injection
            if flow_mode_inputs:
                # TODO: Implement create_input_schema_from_dict in lfx
                args_schema = None
            elif tool_mode_inputs:
                # TODO: Implement create_input_schema in lfx
                args_schema = None
            elif getattr(output, "required_inputs", None):
                inputs = [
                    self.component.get_undesrcore_inputs()[input_name]
                    for input_name in output.required_inputs
                    if getattr(self.component, input_name) is None
                ]
                # If any of the required inputs are not in tool mode, this means
                # that when the tool is called it will raise an error.
                if not all(getattr(_input, "tool_mode", False) for _input in inputs):
                    non_tool_mode_inputs = [
                        input_.name
                        for input_ in inputs
                        if not getattr(input_, "tool_mode", False) and input_.name is not None
                    ]
                    non_tool_mode_inputs_str = ", ".join(non_tool_mode_inputs)
                    msg = (
                        f"Output '{output.name}' requires inputs that are not in tool mode. "
                        f"The following inputs are not in tool mode: {non_tool_mode_inputs_str}. "
                        "Please ensure all required inputs are set to tool mode."
                    )
                    raise ValueError(msg)
                # TODO: Implement create_input_schema in lfx
                args_schema = None
            else:
                # TODO: Implement create_input_schema in lfx
                args_schema = None

            name = f"{output.method}".strip(".")
            formatted_name = _format_tool_name(name)
            event_manager = getattr(self.component, "_event_manager", None)

            if asyncio.iscoroutinefunction(output_method):
                tools.append(
                    StructuredTool(
                        name=formatted_name,
                        description=build_description(self.component),
                        coroutine=_build_output_async_function(self.component, output_method, event_manager),
                        args_schema=args_schema,
                        handle_tool_error=True,
                        callbacks=callbacks,
                        tags=[formatted_name],
                        metadata={
                            "display_name": formatted_name,
                            "display_description": build_description(self.component),
                        },
                    )
                )
            else:
                tools.append(
                    StructuredTool(
                        name=formatted_name,
                        description=build_description(self.component),
                        func=_build_output_function(self.component, output_method, event_manager),
                        args_schema=args_schema,
                        handle_tool_error=True,
                        callbacks=callbacks,
                        tags=[formatted_name],
                        metadata={
                            "display_name": formatted_name,
                            "display_description": build_description(self.component),
                        },
                    )
                )

        if len(tools) == 1 and (tool_name or tool_description):
            tool = tools[0]
            tool.name = _format_tool_name(str(tool_name)) or tool.name
            tool.description = tool_description or tool.description
            tool.tags = [tool.name]
        elif flow_mode_inputs and (tool_name or tool_description):
            for tool in tools:
                tool.name = _format_tool_name(str(tool_name) + "_" + str(tool.name)) or tool.name
                tool.description = (
                    str(tool_description) + " Output details: " + str(tool.description)
                ) or tool.description
                tool.tags = [tool.name]
        elif tool_name or tool_description:
            msg = (
                "When passing a tool name or description, there must be only one tool, "
                f"but {len(tools)} tools were found."
            )
            raise ValueError(msg)
        return tools

    def get_tools_metadata_dictionary(self) -> dict:
        """Get tools metadata dictionary."""
        if isinstance(self.metadata, pd.DataFrame):
            try:
                return {
                    record["tags"][0]: record
                    for record in self.metadata.to_dict(orient="records")
                    if record.get("tags")
                }
            except (KeyError, IndexError) as e:
                msg = "Error processing metadata records: " + str(e)
                raise ValueError(msg) from e
        return {}

    def update_tools_metadata(
        self,
        tools: list[BaseTool | StructuredTool],
    ) -> list[BaseTool]:
        """Update tools metadata."""
        # update the tool_name and description according to the name and description mentioned in the list
        if isinstance(self.metadata, pd.DataFrame):
            metadata_dict = self.get_tools_metadata_dictionary()
            filtered_tools = []
            for tool in tools:
                if isinstance(tool, StructuredTool | BaseTool) and tool.tags:
                    try:
                        tag = tool.tags[0]
                    except IndexError:
                        msg = "Tool tags cannot be empty."
                        raise ValueError(msg) from None
                    if tag in metadata_dict:
                        tool_metadata = metadata_dict[tag]
                        # Only include tools with status=True
                        if tool_metadata.get("status", True):
                            tool.name = tool_metadata.get("name", tool.name)
                            tool.description = tool_metadata.get("description", tool.description)
                            if tool_metadata.get("commands"):
                                tool.description = _add_commands_to_tool_description(
                                    tool.description, tool_metadata.get("commands")
                                )
                            filtered_tools.append(tool)
                else:
                    msg = f"Expected a StructuredTool or BaseTool, got {type(tool)}"
                    raise TypeError(msg)
            return filtered_tools
        return tools

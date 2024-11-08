from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING, Literal

from langchain_core.tools import ToolException
from langchain_core.tools.structured import StructuredTool
from loguru import logger
from pydantic import BaseModel

from langflow.base.tools.constants import TOOL_OUTPUT_NAME
from langflow.io.schema import create_input_schema
from langflow.schema.data import Data
from langflow.schema.message import Message

if TYPE_CHECKING:
    from collections.abc import Callable

    from langchain_core.callbacks import Callbacks
    from langchain_core.tools import BaseTool

    from langflow.custom.custom_component.component import Component
    from langflow.events.event_manager import EventManager
    from langflow.inputs.inputs import InputTypes
    from langflow.io import Output
    from langflow.schema.content_block import ContentBlock


def _get_input_type(_input: InputTypes):
    if _input.input_types:
        if len(_input.input_types) == 1:
            return _input.input_types[0]
        return " | ".join(_input.input_types)
    return _input.field_type


def build_description(component: Component, output: Output) -> str:
    if not output.required_inputs:
        logger.warning(f"Output {output.name} does not have required inputs defined")

    if output.required_inputs:
        args = ", ".join(
            sorted(
                [
                    f"{input_name}: {_get_input_type(component._inputs[input_name])}"
                    for input_name in output.required_inputs
                ]
            )
        )
    else:
        args = ""
    return f"{output.method}({args}) - {component.description}"


def send_message_noop(
    message: Message,
    text: str | None = None,  # noqa: ARG001
    background_color: str | None = None,  # noqa: ARG001
    text_color: str | None = None,  # noqa: ARG001
    icon: str | None = None,  # noqa: ARG001
    content_blocks: list[ContentBlock] | None = None,  # noqa: ARG001
    format_type: Literal["default", "error", "warning", "info"] = "default",  # noqa: ARG001
    id_: str | None = None,  # noqa: ARG001
    *,
    allow_markdown: bool = True,  # noqa: ARG001
) -> Message:
    """No-op implementation of send_message."""
    return message


def patch_components_send_message(component: Component):
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


def _build_output_function(component: Component, output_method: Callable, event_manager: EventManager | None = None):
    def output_function(*args, **kwargs):
        try:
            if event_manager:
                event_manager.on_build_start(data={"id": component._id})
            component.set(*args, **kwargs)
            result = output_method()
            if event_manager:
                event_manager.on_build_end(data={"id": component._id})
        except Exception as e:
            raise ToolException(e) from e

        if isinstance(result, Message):
            return result.get_text()
        if isinstance(result, Data):
            return result.data
        if isinstance(result, BaseModel):
            return result.model_dump()
        return result

    return _patch_send_message_decorator(component, output_function)


def _build_output_async_function(
    component: Component, output_method: Callable, event_manager: EventManager | None = None
):
    async def output_function(*args, **kwargs):
        try:
            if event_manager:
                event_manager.on_build_start(data={"id": component._id})
            component.set(*args, **kwargs)
            result = await output_method()
            if event_manager:
                event_manager.on_build_end(data={"id": component._id})
        except Exception as e:
            raise ToolException(e) from e
        if isinstance(result, Message):
            return result.get_text()
        if isinstance(result, Data):
            return result.data
        if isinstance(result, BaseModel):
            return result.model_dump()
        return result

    return _patch_send_message_decorator(component, output_function)


def _format_tool_name(name: str):
    # format to '^[a-zA-Z0-9_-]+$'."
    # to do that we must remove all non-alphanumeric characters

    return re.sub(r"[^a-zA-Z0-9_-]", "-", name)


class ComponentToolkit:
    def __init__(self, component: Component):
        self.component = component

    def get_tools(
        self, tool_name: str | None = None, tool_description: str | None = None, callbacks: Callbacks | None = None
    ) -> list[BaseTool]:
        tools = []
        for output in self.component.outputs:
            if output.name == TOOL_OUTPUT_NAME:
                continue

            if not output.method:
                msg = f"Output {output.name} does not have a method defined"
                raise ValueError(msg)

            output_method: Callable = getattr(self.component, output.method)
            args_schema = None
            tool_mode_inputs = [_input for _input in self.component.inputs if getattr(_input, "tool_mode", False)]
            if output.required_inputs:
                inputs = [
                    self.component._inputs[input_name]
                    for input_name in output.required_inputs
                    if getattr(self.component, input_name) is None
                ]
                # If any of the required inputs are not in tool mode, this means
                # that when the tool is called it will raise an error.
                # so we should raise an error here.
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
                args_schema = create_input_schema(inputs)
            elif tool_mode_inputs:
                args_schema = create_input_schema(tool_mode_inputs)
            else:
                args_schema = create_input_schema(self.component.inputs)
            name = f"{self.component.name}.{output.method}"
            formatted_name = _format_tool_name(name)
            event_manager = self.component._event_manager
            if asyncio.iscoroutinefunction(output_method):
                tools.append(
                    StructuredTool(
                        name=formatted_name,
                        description=build_description(self.component, output),
                        coroutine=_build_output_async_function(self.component, output_method, event_manager),
                        args_schema=args_schema,
                        handle_tool_error=True,
                        callbacks=callbacks,
                    )
                )
            else:
                tools.append(
                    StructuredTool(
                        name=formatted_name,
                        description=build_description(self.component, output),
                        func=_build_output_function(self.component, output_method, event_manager),
                        args_schema=args_schema,
                        handle_tool_error=True,
                        callbacks=callbacks,
                    )
                )
        if len(tools) == 1 and (tool_name or tool_description):
            tool = tools[0]
            tool.name = tool_name or tool.name
            tool.description = tool_description or tool.description
        elif tool_name or tool_description:
            msg = (
                "When passing a tool name or description, there must be only one tool, "
                f"but {len(tools)} tools were found."
            )
            raise ValueError(msg)
        return tools

from __future__ import annotations

import asyncio
import re
from copy import deepcopy
from typing import TYPE_CHECKING

import pandas as pd
from langchain_core.tools import BaseTool, ToolException
from langchain_core.tools.structured import StructuredTool

from lfx.base.tools.constants import TOOL_OUTPUT_NAME
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.message import Message
from lfx.serialization.serialization import serialize

if TYPE_CHECKING:
    from collections.abc import Callable

    from langchain_core.callbacks import Callbacks

    from lfx.custom.custom_component.component import Component
    from lfx.events.event_manager import EventManager
    from lfx.inputs.inputs import InputTypes
    from lfx.io import Output
    from lfx.schema.dotdict import dotdict

TOOL_TYPES_SET = {"Tool", "BaseTool", "StructuredTool"}


def _get_input_type(input_: InputTypes):
    if input_.input_types:
        if len(input_.input_types) == 1:
            return input_.input_types[0]
        return " | ".join(input_.input_types)
    return input_.field_type


def build_description(component: Component, output=None) -> str:
    """Build tool description, preferring output-level info over component description."""
    if output and getattr(output, "info", None):
        return output.info
    return component.description or ""


async def send_message_noop(
    message: Message,
    id_: str | None = None,  # noqa: ARG001
    *,
    skip_db_update: bool = False,  # noqa: ARG001
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


def _build_output_function(
    component: Component,
    output_method: Callable,
    event_manager: EventManager | None = None,
    output_name: str = TOOL_OUTPUT_NAME,
):
    method_name = output_method.__name__
    # Capture tool_mode input names so positional args can be mapped to kwargs
    _tool_input_names = [inp.name for inp in component.inputs if getattr(inp, "tool_mode", False)]

    def output_function(*args, **kwargs):
        # Map positional args to keyword args using tool_mode input names
        if args:
            for i, val in enumerate(args):
                if i < len(_tool_input_names) and _tool_input_names[i] not in kwargs:
                    kwargs[_tool_input_names[i]] = val
        # Create an isolated copy to prevent race conditions when this
        # tool is invoked concurrently by an agent (GitHub issue #8791)
        comp = deepcopy(component)
        local_method = getattr(comp, method_name, output_method)
        build_started = False
        result = None
        try:
            if event_manager:
                event_manager.on_build_start(data={"id": comp.get_id()})
                build_started = True
            comp.set_event_manager(event_manager)
            comp.set_current_output(output_name)
            comp.set(**kwargs)
            result = local_method()
        except Exception as e:
            logger.error(
                "Component %s failed during tool mode execution: %s",
                comp.get_id(),
                e,
                exc_info=True,
            )
            raise ToolException(str(e)) from e
        finally:
            comp.set_current_output("")
            comp.set_event_manager(None)
            if build_started and event_manager:
                event_manager.on_build_end(data={"id": comp.get_id()})

        if isinstance(result, Message):
            return result.get_text()
        if isinstance(result, Data):
            return result.data
        if isinstance(result, pd.DataFrame):
            return result
        # removing the model_dump() call here because it is not serializable
        return serialize(result)

    return _patch_send_message_decorator(component, output_function)


def _build_output_async_function(
    component: Component,
    output_method: Callable,
    event_manager: EventManager | None = None,
    output_name: str = TOOL_OUTPUT_NAME,
):
    method_name = output_method.__name__
    # Capture tool_mode input names so positional args can be mapped to kwargs
    _tool_input_names = [inp.name for inp in component.inputs if getattr(inp, "tool_mode", False)]

    async def output_function(*args, **kwargs):
        # Map positional args to keyword args using tool_mode input names
        if args:
            for i, val in enumerate(args):
                if i < len(_tool_input_names) and _tool_input_names[i] not in kwargs:
                    kwargs[_tool_input_names[i]] = val
        # Create an isolated copy to prevent race conditions when this
        # tool is invoked concurrently by an agent (GitHub issue #8791)
        comp = deepcopy(component)
        local_method = getattr(comp, method_name, output_method)
        build_started = False
        result = None
        try:
            if event_manager:
                event_manager.on_build_start(data={"id": comp.get_id()})
                build_started = True
            comp.set_event_manager(event_manager)
            comp.set_current_output(output_name)
            comp.set(**kwargs)
            result = await local_method()
        except Exception as e:
            logger.error(
                "Component %s failed during tool mode execution: %s",
                comp.get_id(),
                e,
                exc_info=True,
            )
            raise ToolException(str(e)) from e
        finally:
            comp.set_current_output("")
            comp.set_event_manager(None)
            if build_started and event_manager:
                event_manager.on_build_end(data={"id": comp.get_id()})
        if isinstance(result, Message):
            return result.get_text()
        if isinstance(result, Data):
            return result.data
        if isinstance(result, pd.DataFrame):
            return result
        # removing the model_dump() call here because it is not serializable
        return serialize(result)

    return _patch_send_message_decorator(component, output_function)


def _format_tool_name(name: str):
    # format to '^[a-zA-Z0-9_-]+$'."
    # to do that we must remove all non-alphanumeric characters

    return re.sub(r"[^a-zA-Z0-9_-]", "-", name)


# Method names that carry no semantic signal about what the tool DOES. When
# a single-output component uses one of these, the LLM-facing tool name is
# derived from the component class name instead — the class name is the
# user's stated intent (e.g. ``RandomMenuItem``, ``DrinkPrice``) and is
# always more informative than ``output``/``process``. Kept narrow on
# purpose: descriptive method names (``get_forecast``, ``search_products``)
# must NOT be overridden, and multi-output components must NOT be
# collapsed to a single name (that would shadow tools).
_GENERIC_OUTPUT_METHOD_NAMES = frozenset(
    {"output", "process", "build_output", "run", "execute", "main", "handler", "build_result"}
)


def _class_name_to_tool_name(class_name: str) -> str:
    """CamelCase → snake_case, preserving acronym boundaries.

    Examples:
        RandomMenuItem  → random_menu_item
        DrinkPrice      → drink_price
        HTTPClient      → http_client
        S3Bucket        → s3_bucket
        MyXMLParser     → my_xml_parser
        Already_snake   → already_snake (passthrough)
    """
    # Insert underscore between acronym and following CamelCase word
    # ("HTTPClient" → "HTTP_Client", "MyXMLParser" → "My_XMLParser")
    step1 = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", class_name)
    # Insert underscore between lowercase/digit and uppercase
    # ("RandomMenu" → "Random_Menu", "S3Bucket" → "S3_Bucket")
    step2 = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", step1)
    return step2.lower()


def _derive_tool_name(component: Component, output_method: str, outputs: list[Output]) -> str:
    """Pick a tool name that an LLM can act on.

    Defaults to the output's method name (existing contract). Falls back to
    the snake_cased component class name only when:

    1. The method name is generic (``output``/``process``/...) — i.e. it
       carries no semantic signal.
    2. The component has exactly one tool-exposed output. Multi-output
       components keep method-derived names so each tool stays distinct.
    """
    if output_method in _GENERIC_OUTPUT_METHOD_NAMES and len(outputs) == 1:
        return _class_name_to_tool_name(type(component).__name__)
    return output_method


def _add_commands_to_tool_description(tool_description: str, commands: str):
    return f"very_time you see one of those commands {commands} run the tool. tool description is {tool_description}"


class ComponentToolkit:
    def __init__(self, component: Component, metadata: pd.DataFrame | None = None):
        self.component = component
        self.metadata = metadata

    def _should_skip_output(self, output: Output) -> bool:
        """Determines if an output should be skipped when creating tools.

        Args:
            output (Output): The output to check.

        Returns:
            bool: True if the output should be skipped, False otherwise.

        The output will be skipped if:
        - tool_mode is False (the user opted this output out of tool exposure)
        - it is the SYNTHETIC output that ``_append_tool_to_outputs_map`` adds
          when the component is flipped to tool mode (name + method + types
          all match — those three together uniquely identify the synthetic,
          whereas matching on name alone wrongly skipped LLM-generated user
          components whose Output happened to be named ``component_as_tool``,
          producing an empty tool list — production failure 2026-05-27).
        - the output is already a Tool-typed handoff (anything in
          ``TOOL_TYPES_SET``) — wrapping a Tool in another Tool is a no-op.
        """
        if not output.tool_mode:
            return True
        # Synthetic-tool sentinel: name + method + types ALL match. Anything
        # less is a user-declared output that happens to share the name.
        is_synthetic_tool = (
            output.name == TOOL_OUTPUT_NAME
            and output.method == "to_toolkit"
            and any(tool_type in output.types for tool_type in TOOL_TYPES_SET)
        )
        if is_synthetic_tool:
            return True
        # Already-a-Tool outputs short-circuit too.
        return any(tool_type in output.types for tool_type in TOOL_TYPES_SET)

    def get_tools(
        self,
        tool_name: str | None = None,
        tool_description: str | None = None,
        callbacks: Callbacks | None = None,
        flow_mode_inputs: list[dotdict] | None = None,
    ) -> list[BaseTool]:
        from lfx.io.schema import create_input_schema, create_input_schema_from_dict

        tools = []
        # Resolve up front: tool_mode-eligible outputs gate the class-name
        # fallback below (only safe for single-output components).
        eligible_outputs = [o for o in self.component.outputs if not self._should_skip_output(o)]
        for output in eligible_outputs:
            if not output.method:
                msg = f"Output {output.name} does not have a method defined"
                raise ValueError(msg)

            output_method: Callable = getattr(self.component, output.method)
            args_schema = None
            tool_mode_inputs = [_input for _input in self.component.inputs if getattr(_input, "tool_mode", False)]
            if flow_mode_inputs:
                args_schema = create_input_schema_from_dict(
                    inputs=flow_mode_inputs,
                    param_key="flow_tweak_data",
                )
            elif tool_mode_inputs:
                args_schema = create_input_schema(tool_mode_inputs)
            elif output.required_inputs:
                inputs = [
                    self.component.get_underscore_inputs()[input_name]
                    for input_name in output.required_inputs
                    if getattr(self.component, input_name) is None
                ]
                # If any of the required inputs are not in tool mode, this means
                # that when the tool is called it will raise an error.
                # so we should raise an error here.
                # TODO: This logic might need to be improved, example if the required is an api key.
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

            else:
                args_schema = create_input_schema(self.component.inputs)

            name = _derive_tool_name(self.component, f"{output.method}".strip("."), eligible_outputs)
            formatted_name = _format_tool_name(name)
            event_manager = self.component.get_event_manager()
            if asyncio.iscoroutinefunction(output_method):
                tools.append(
                    StructuredTool(
                        name=formatted_name,
                        description=build_description(self.component, output),
                        coroutine=_build_output_async_function(
                            self.component, output_method, event_manager, TOOL_OUTPUT_NAME
                        ),
                        args_schema=args_schema,
                        handle_tool_error=True,
                        callbacks=callbacks,
                        tags=[formatted_name],
                        metadata={
                            "display_name": formatted_name,
                            "display_description": build_description(self.component, output),
                        },
                    )
                )
            else:
                tools.append(
                    StructuredTool(
                        name=formatted_name,
                        description=build_description(self.component, output),
                        func=_build_output_function(self.component, output_method, event_manager, TOOL_OUTPUT_NAME),
                        args_schema=args_schema,
                        handle_tool_error=True,
                        callbacks=callbacks,
                        tags=[formatted_name],
                        metadata={
                            "display_name": formatted_name,
                            "display_description": build_description(self.component, output),
                        },
                    )
                )
        if len(tools) == 1 and (tool_name or tool_description):
            tool = tools[0]
            tool.name = _format_tool_name(str(tool_name)) or tool.name
            tool.description = tool_description or tool.description
            tool.tags = [tool.name]
        elif (tool_name or tool_description) and (flow_mode_inputs or len(tools) > 1):
            for tool in tools:
                tool.name = _format_tool_name(str(tool_name) + "_" + str(tool.name)) or tool.name
                # Only prepend an explicit tool_description. Without one, keep the
                # output-derived description so it stays equal to display_description
                # and the Actions-panel merge logic can detect real user edits.
                if tool_description:
                    tool.description = f"{tool_description} Output details: {tool.description}"
                tool.tags = [tool.name]
        return tools

    def get_tools_metadata_dictionary(self) -> dict:
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
        # update the tool_name and description according to the name and secriotion mentioned in the list
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

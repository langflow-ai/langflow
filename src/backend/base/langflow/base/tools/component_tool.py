from __future__ import annotations

import re
from typing import TYPE_CHECKING

from langchain_core.tools import ToolException
from langchain_core.tools.structured import StructuredTool
from loguru import logger

from langflow.base.tools.constants import TOOL_OUTPUT_NAME
from langflow.io.schema import create_input_schema

if TYPE_CHECKING:
    from collections.abc import Callable

    from langchain_core.tools import BaseTool

    from langflow.custom.custom_component.component import Component
    from langflow.events.event_manager import EventManager
    from langflow.inputs.inputs import InputTypes
    from langflow.io import Output


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


def _build_output_function(component: Component, output_method: Callable, event_manager: EventManager | None = None):
    def output_function(*args, **kwargs):
        # set the component with the arguments
        # set functionality was updatedto handle list of components and other values separately
        try:
            if event_manager:
                event_manager.on_build_start(data={"id": component._id})
            component.set(*args, **kwargs)
            result = output_method()
            if event_manager:
                event_manager.on_build_end(data={"id": component._id})
        except Exception as e:
            raise ToolException(e) from e
        else:
            return result

    return output_function


def _format_tool_name(name: str):
    # format to '^[a-zA-Z0-9_-]+$'."
    # to do that we must remove all non-alphanumeric characters

    return re.sub(r"[^a-zA-Z0-9_-]", "-", name)


class ComponentToolkit:
    def __init__(self, component: Component):
        self.component = component

    def get_tools(self) -> list[BaseTool]:
        tools = []
        for output in self.component.outputs:
            if output.name == TOOL_OUTPUT_NAME:
                continue

            if not output.method:
                msg = f"Output {output.name} does not have a method defined"
                raise ValueError(msg)

            output_method: Callable = getattr(self.component, output.method)
            args_schema = None
            if output.required_inputs:
                inputs = [self.component._inputs[input_name] for input_name in output.required_inputs]
                args_schema = create_input_schema(inputs)
            else:
                args_schema = create_input_schema(self.component.inputs)
            name = f"{self.component.name}.{output.method}"
            formatted_name = _format_tool_name(name)
            tools.append(
                StructuredTool(
                    name=formatted_name,
                    description=build_description(component=self.component, output=output),
                    func=_build_output_function(
                        component=self.component,
                        output_method=output_method,
                        event_manager=self.component._event_manager,
                    ),
                    args_schema=args_schema,
                )
            )
        return tools

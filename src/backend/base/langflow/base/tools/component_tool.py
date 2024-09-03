from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from langchain_core.tools import BaseTool
from langchain_core.tools.base import BaseToolkit
from langchain_core.tools.structured import StructuredTool

from langflow.base.tools.constants import TOOL_OUTPUT_NAME
from langflow.io.schema import create_input_schema

if TYPE_CHECKING:
    from langflow.custom.custom_component.component import Component
    from langflow.inputs.inputs import InputTypes
    from langflow.io import Output


def _get_input_type(input: "InputTypes"):
    if input.input_types:
        if len(input.input_types) == 1:
            return input.input_types[0]
        return " | ".join(input.input_types)
    return input.field_type


def build_description(component: "Component", output: "Output"):
    args = ", ".join(
        sorted(
            [f"{input_name}: {_get_input_type(component._inputs[input_name])}" for input_name in output.required_inputs]
        )
    )
    return f"{output.method}({args}) - {component.description}"


def _build_output_function(component: "Component", output_method: Callable):
    def output_function(*args, **kwargs):
        component.set(*args, **kwargs)
        return output_method()

    return output_function


class ComponentToolkit(BaseToolkit, arbitrary_types_allowed=True):  # type: ignore
    component: "Component"

    def get_tools(self) -> list[BaseTool]:
        tools = []
        for output in self.component.outputs:
            if output.name == TOOL_OUTPUT_NAME:
                continue
            output_method: Callable = getattr(self.component, output.method)
            args_schema = None
            if output.required_inputs:
                inputs = [self.component._inputs[input_name] for input_name in output.required_inputs]
                args_schema = create_input_schema(inputs)
            else:
                args_schema = create_input_schema(self.component.inputs)
            tools.append(
                StructuredTool(
                    name=f"{self.component.name}.{output.method}",
                    description=build_description(self.component, output),
                    func=_build_output_function(self.component, output_method),
                    args_schema=args_schema,
                )
            )
        return tools

from typing import Callable

from langchain_core.tools import BaseTool
from langchain_core.tools.base import BaseToolkit
from langchain_core.tools.structured import StructuredTool

from langflow.custom.custom_component.component import Component
from langflow.io import Output
from langflow.io.schema import create_input_schema


def build_description(component: Component, output: Output):
    return f"Description: {component.description}\nOutput Types: {output.types}"


def _build_output_function(component: Component, output_method: Callable):
    def output_function(*args, **kwargs):
        component.set(*args, **kwargs)
        return output_method()

    return output_function


class ComponentToolkit(BaseToolkit, arbitrary_types_allowed=True):  # type: ignore
    component: Component

    def get_tools(self) -> list[BaseTool]:
        tools = []
        for output in self.component.outputs:
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

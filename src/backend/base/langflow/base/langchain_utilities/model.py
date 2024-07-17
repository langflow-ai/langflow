from abc import abstractmethod
from typing import Union

from langflow.custom import Component
from langflow.field_typing import Tool
from langflow.io import Output
from langflow.schema import Data


class LCToolComponent(Component):
    trace_type = "tool"
    outputs = [
        Output(name="api_run_model", display_name="Data", method="run_model"),
        Output(name="api_build_tool", display_name="Tool", method="build_tool"),
    ]

    def _validate_outputs(self):
        required_output_methods = ["run_model", "build_tool"]
        output_names = [output.name for output in self.outputs]
        for method_name in required_output_methods:
            if method_name not in output_names:
                raise ValueError(f"Output with name '{method_name}' must be defined.")
            elif not hasattr(self, method_name):
                raise ValueError(f"Method '{method_name}' must be defined.")

    @abstractmethod
    def run_model(self) -> Union[Data, list[Data]]:
        """
        Run model and return the output.
        """
        pass

    @abstractmethod
    def build_tool(self) -> Tool:
        """
        Build the tool.
        """
        pass

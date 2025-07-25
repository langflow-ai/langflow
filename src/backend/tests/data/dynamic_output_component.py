from typing import Any

from lfx.custom import Component
from lfx.io import BoolInput, MessageTextInput, Output
from lfx.schema import Data


class DynamicOutputComponent(Component):
    display_name = "Dynamic Output Component"
    description = "Use as a template to create your own component."
    documentation: str = "https://docs.langflow.org/components-custom-components"
    icon = "custom_components"
    name = "DynamicOutputComponent"

    inputs = [
        MessageTextInput(name="input_value", display_name="Input Value", value="Hello, World!"),
        BoolInput(name="show_output", display_name="Show Output", value=True, real_time_refresh=True),
    ]

    outputs = [
        Output(display_name="Output", name="output", method="build_output"),
    ]

    def update_outputs(self, frontend_node: dict, field_name: str, field_value: Any):
        if field_name == "show_output":
            if field_value:
                frontend_node["outputs"].append(
                    Output(display_name="Tool Output", name="tool_output", method="build_output")
                )
            else:
                # remove the output
                frontend_node["outputs"] = [
                    output for output in frontend_node["outputs"] if output["name"] != "tool_output"
                ]
        return frontend_node

    def build_output(self) -> Data:
        data = Data(value=self.input_value)
        self.status = data
        return data

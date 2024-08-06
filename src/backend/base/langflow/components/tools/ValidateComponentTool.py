from typing import cast

from langchain.tools import StructuredTool

from langflow.base.langchain_utilities.model import LCToolComponent
from langflow.components.helpers.component_code_validator import ComponentCodeValidator
from langflow.field_typing import Tool
from langflow.io import MessageTextInput, MultilineInput
from langflow.schema import Data


class ValidateComponentTool(LCToolComponent):
    display_name = "Validate Component Tool"
    description = "Validates the code of a component."
    name = "ValidateComponentTool"

    inputs = [
        MessageTextInput(
            name="tool_name", display_name="Tool Name", required=True, value="Langflow Component Code Validator"
        ),
        MessageTextInput(
            name="tool_description",
            display_name="Tool Description",
            required=True,
            value="Validates the code of a component.",
        ),
        MultilineInput(
            name="component_code",
            display_name="Component Code",
            required=False,
            info="Only required if you plan to use the Data output.",
        ),
    ]

    def run_model(self) -> Data | list[Data]:
        tool = self.build_tool()
        data_json = tool.invoke(self.component_code)
        return Data.from_json(data_json)

    def build_tool(self) -> Tool:
        def validate_code(component_code: str) -> str:
            """Validates the code of a component."""
            component = ComponentCodeValidator()

            component.set(component_code=component_code)
            data_obj = component.validate_code()
            return data_obj.model_dump_json()

        tool = StructuredTool.from_function(func=validate_code, name=self.tool_name, description=self.tool_description)
        return cast(Tool, tool)

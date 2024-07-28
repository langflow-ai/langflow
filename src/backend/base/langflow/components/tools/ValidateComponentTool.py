from typing import cast

from langchain.tools import StructuredTool

from langflow.components.helpers.component_code_validator import ComponentCodeValidator
from langflow.custom import Component
from langflow.field_typing import Tool
from langflow.inputs import MessageTextInput


class ValidateComponentTool(Component):
    display_name = "Validate Component Tool"
    description = "Validates the code of a component."
    name = "ValidateComponentTool"

    inputs = [
        MessageTextInput(name="tool_name", display_name="Tool Name", required=True),
        MessageTextInput(name="tool_description", display_name="Tool Description", required=True),
    ]

    def build_tool(self) -> Tool:
        def validate_code(component_code: str) -> str:
            """Validates the code of a component."""
            component = ComponentCodeValidator()
            component.initialize(parameters={"component_code": component_code})
            component.validate_code()

        tool = StructuredTool.from_function(func=validate_code, name=self.tool_name, description=self.tool_description)
        return cast(Tool, tool)

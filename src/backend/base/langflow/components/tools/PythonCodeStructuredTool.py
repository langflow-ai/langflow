import ast
from typing import Any, Dict

from langchain.agents import Tool
from langflow.inputs.inputs import MultilineInput, MessageTextInput, BoolInput, DropdownInput
from langchain_core.tools import StructuredTool
from langflow.io import Output

from langflow.custom import Component
from langflow.schema.dotdict import dotdict


class PythonCodeStructuredTool(Component):
    display_name = "Python Code Tool"
    description = "structuredtool dataclass code to tool"
    documentation = "https://python.langchain.com/docs/modules/tools/custom_tools/#structuredtool-dataclass"
    name = "PythonCodeStructuredTool"
    icon = "🐍"
    field_order = ["name", "description", "tool_code", "return_direct", "tool_function", "tool_class"]
    inputs = [
        MultilineInput(
            name="tool_code",
            display_name="Tool Code",
            info="Enter the dataclass code.",
            placeholder="def my_function(args):\n    pass",
            refresh_button=True,
        ),
        MessageTextInput(name="tool_name", display_name="Tool Name", info="Enter the name of the tool."),
        MessageTextInput(
            name="tool_description", display_name="Description", info="Enter the description of the tool."
        ),
        BoolInput(
            name="return_direct",
            display_name="Return Directly",
            info="Should the tool return the function output directly?",
        ),
        DropdownInput(
            name="tool_function",
            display_name="Tool Function",
            info="Select the function for additional expressions.",
            options=[],
            refresh_button=True,
        ),
        DropdownInput(
            name="tool_class",
            display_name="Tool Class",
            info="Select the class for additional expressions.",
            options=[],
            required=False,
            refresh_button=True,
        ),
    ]
    outputs = [
        Output(display_name="Tool", name="result_tool", method="build_tool"),
    ]

    def parse_source_name(self, code: str) -> Dict:
        parsed_code = ast.parse(code)
        class_names = [node.name for node in parsed_code.body if isinstance(node, ast.ClassDef)]
        function_names = [node.name for node in parsed_code.body if isinstance(node, ast.FunctionDef)]
        return {"class": class_names, "function": function_names}

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None) -> dotdict:
        if field_name == "tool_code" or field_name == "tool_function" or field_name == "tool_class":
            try:
                names = self.parse_source_name(build_config.tool_code.value)
                build_config["tool_function"]["options"] = names["function"]
                build_config["tool_class"]["options"] = names["class"]
            except Exception as e:
                self.status = f"Failed to extract class names: {str(e)}"
                build_config["tool_function"]["options"] = ["Failed to parse", str(e)]
                build_config["tool_class"]["options"] = ["Failed to parse", str(e)]
        return build_config

    async def build_tool(self) -> Tool:
        local_namespace = {}  # type: ignore
        exec(self.tool_code, globals(), local_namespace)

        func = local_namespace[self.tool_function]
        _class = None

        if self.tool_class:
            _class = local_namespace[self.tool_class]

        tool = StructuredTool.from_function(
            func=func,
            args_schema=_class,
            name=self.tool_name,
            description=self.tool_description,
            return_direct=self.return_direct,
        )
        return tool  # type: ignore

    def post_code_processing(self, new_frontend_node: dict, current_frontend_node: dict):
        """
        This function is called after the code validation is done.
        """
        frontend_node = super().post_code_processing(new_frontend_node, current_frontend_node)
        frontend_node["template"] = self.update_build_config(
            frontend_node["template"], frontend_node["template"]["tool_code"]["value"], "tool_code"
        )
        frontend_node = super().post_code_processing(new_frontend_node, current_frontend_node)
        return frontend_node

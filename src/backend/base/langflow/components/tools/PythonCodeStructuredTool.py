import ast
from typing import Any, Dict, List, Optional

from langchain.agents import Tool
from langchain_core.tools import StructuredTool

from langflow.custom import CustomComponent
from langflow.schema.dotdict import dotdict


class PythonCodeStructuredTool(CustomComponent):
    display_name = "PythonCodeTool"
    description = "structuredtool dataclass code to tool"
    documentation = "https://python.langchain.com/docs/modules/tools/custom_tools/#structuredtool-dataclass"
    name = "PythonCodeStructuredTool"
    icon = "🐍"
    field_order = ["name", "description", "tool_code", "return_direct", "tool_function", "tool_class"]

    def build_config(self) -> Dict[str, Any]:
        return {
            "tool_code": {
                "display_name": "Tool Code",
                "info": "Enter the dataclass code.",
                "placeholder": "def my_function(args):\n    pass",
                "multiline": True,
                "refresh_button": True,
                "field_type": "code",
            },
            "name": {
                "display_name": "Tool Name",
                "info": "Enter the name of the tool.",
            },
            "description": {
                "display_name": "Description",
                "info": "Provide a brief description of what the tool does.",
            },
            "return_direct": {
                "display_name": "Return Directly",
                "info": "Should the tool return the function output directly?",
            },
            "tool_function": {
                "display_name": "Tool Function",
                "info": "Select the function for additional expressions.",
                "options": [],
                "refresh_button": True,
            },
            "tool_class": {
                "display_name": "Tool Class",
                "info": "Select the class for additional expressions.",
                "options": [],
                "refresh_button": True,
                "required": False,
            },
        }

    def parse_source_name(self, code: str) -> Dict:
        parsed_code = ast.parse(code)
        class_names = [node.name for node in parsed_code.body if isinstance(node, ast.ClassDef)]
        function_names = [node.name for node in parsed_code.body if isinstance(node, ast.FunctionDef)]
        return {"class": class_names, "function": function_names}

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None) -> dotdict:
        if field_name == "tool_code" or field_name == "tool_function" or field_name == "tool_class":
            try:
                names = self.parse_source_name(build_config.tool_code.value)
                build_config.tool_class.options = names["class"]
                build_config.tool_function.options = names["function"]
            except Exception as e:
                self.status = f"Failed to extract class names: {str(e)}"
                build_config.tool_class.options = ["Failed to parse", str(e)]
                build_config.tool_function.options = []
        return build_config

    async def build(
        self,
        tool_code: str,
        name: str,
        description: str,
        tool_function: List[str],
        return_direct: bool,
        tool_class: Optional[List[str]] = None,
    ) -> Tool:
        local_namespace = {}  # type: ignore
        exec(tool_code, globals(), local_namespace)

        func = local_namespace[tool_function]
        _class = None

        if tool_class:
            _class = local_namespace[tool_class]

        tool = StructuredTool.from_function(
            func=func, args_schema=_class, name=name, description=description, return_direct=return_direct
        )
        return tool  # type: ignore

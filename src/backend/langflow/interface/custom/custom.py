import re
import ast
import traceback
from typing import Callable, Optional
from fastapi import HTTPException
from langflow.interface.custom.constants import LANGCHAIN_BASE_TYPES

from langflow.utils import validate
from pydantic import BaseModel


class CustomComponent(BaseModel):
    field_config: dict = {}
    code: str
    function: Optional[Callable] = None
    function_entrypoint_name = "build"
    return_type_valid_list = list(LANGCHAIN_BASE_TYPES.keys())
    class_template = {
        "imports": [],
        "class": {"inherited_classes": "", "name": "", "init": "", "attributes": {}},
        "functions": [],
    }

    def __init__(self, **data):
        super().__init__(**data)

    def _handle_import(self, node):
        for alias in node.names:
            module_name = getattr(node, "module", None)
            self.class_template["imports"].append(
                f"{module_name}.{alias.name}" if module_name else alias.name
            )

    def _handle_class(self, node):
        self.class_template["class"].update(
            {
                "name": node.name,
                "inherited_classes": [ast.unparse(base) for base in node.bases],
            }
        )

        attributes = {}  # To store the attributes and their values

        for inner_node in node.body:
            if isinstance(inner_node, ast.Assign):  # An assignment
                for target in inner_node.targets:  # Targets of the assignment
                    if isinstance(target, ast.Name):  # A simple variable
                        # Add the attribute and its value to the dictionary
                        attributes[target.id] = ast.unparse(inner_node.value)
            elif isinstance(inner_node, ast.AnnAssign):  # An annotated assignment
                if isinstance(inner_node.target, ast.Name) and inner_node.value:
                    attributes[inner_node.target.id] = ast.unparse(inner_node.value)

            elif isinstance(inner_node, ast.FunctionDef):
                self._handle_function(inner_node)

        # You can add these attributes to your class_template if you want
        self.class_template["class"]["attributes"] = attributes

    def _handle_function(self, node):
        function_name = node.name
        function_args_str = ast.unparse(node.args)
        function_args = function_args_str.split(", ") if function_args_str else []

        return_type = ast.unparse(node.returns) if node.returns else "None"

        function_data = {
            "name": function_name,
            "arguments": function_args,
            "return_type": return_type,
        }

        if function_name == "__init__":
            self.class_template["class"]["init"] = (
                function_args_str.split(", ") if function_args_str else []
            )
        else:
            self.class_template["functions"].append(function_data)

    def _split_string(self, text):
        """
        Split a string by ':' or '=' and append None until the resulting list has 3 items.

        Parameters:
        text (str): The string to be split.

        Returns:
        list: A list of strings resulting from the split operation,
        padded with None until its length is 3.
        """
        items = [item.strip() for item in re.split(r"[:=]", text) if item.strip()]
        while len(items) < 3:
            items.append(None)

        return items

    def transform_list(self, input_list):
        """
        Transform a list of strings by splitting each string and padding with None.

        Parameters:
        input_list (list): The list of strings to be transformed.

        Returns:
        list: A list of lists, each containing the result of the split operation.
        """
        return [self._split_string(item) for item in input_list]

    def extract_class_info(self):
        try:
            module = ast.parse(self.code)
        except SyntaxError as err:
            raise HTTPException(
                status_code=400,
                detail={"error": err.msg, "traceback": traceback.format_exc()},
            ) from err

        for node in module.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                self._handle_import(node)
            elif isinstance(node, ast.ClassDef):
                self._handle_class(node)

        return self.class_template

    def get_entrypoint_function_args_and_return_type(self):
        data = self.extract_class_info()
        attributes = data.get("class", {}).get("attributes", {})
        functions = data.get("functions", [])
        template_config = self._build_template_config(attributes)

        if build_function := next(
            (f for f in functions if f["name"] == self.function_entrypoint_name),
            None,
        ):
            function_args = build_function.get("arguments", None)
            function_args = self.transform_list(function_args)

            return_type = build_function.get("return_type", None)
        else:
            function_args = None
            return_type = None

        return function_args, return_type, template_config

    def _build_template_config(self, attributes):
        template_config = {}
        if "field_config" in attributes:
            template_config["field_config"] = ast.literal_eval(
                attributes["field_config"]
            )
        if "display_name" in attributes:
            template_config["display_name"] = ast.literal_eval(
                attributes["display_name"]
            )
        if "description" in attributes:
            template_config["description"] = ast.literal_eval(attributes["description"])

        return template_config

    def _class_template_validation(self, code: dict):
        class_name = code.get("class", {}).get("name", None)
        if not class_name:  # this will also check for None, empty string, etc.
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "The main class must have a valid name.",
                    "traceback": "",
                },
            )

        functions = code.get("functions", [])
        build_function = next(
            (f for f in functions if f["name"] == self.function_entrypoint_name),
            None,
        )

        if not build_function:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Invalid entrypoint function name",
                    "traceback": (
                        f"There needs to be at least one entrypoint function named '{self.function_entrypoint_name}'"
                        f" and it needs to return one of the types from this list {str(self.return_type_valid_list)}.",
                    ),
                },
            )

        return_type = build_function.get("return_type")
        if return_type not in self.return_type_valid_list:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Invalid entrypoint function return",
                    "traceback": (
                        f"The entrypoint function return '{return_type}' needs to be an item "
                        f"from this list {str(self.return_type_valid_list)}."
                    ),
                },
            )

        return True

    def get_function(self):
        return validate.create_function(self.code, self.function_entrypoint_name)

    def build(self):
        raise NotImplementedError

    @property
    def data(self):
        return self.extract_class_info()

    def is_check_valid(self):
        return self._class_template_validation(self.data)

    @property
    def args_and_return_type(self):
        return self.get_entrypoint_function_args_and_return_type()

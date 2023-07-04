import ast

from typing import Callable, Optional
from langflow.interface.importing.utils import get_function

from pydantic import BaseModel, validator

from langflow.utils import validate
from langchain.agents.tools import Tool


class Function(BaseModel):
    code: str
    function: Optional[Callable] = None
    imports: Optional[str] = None

    # Eval code and store the function
    def __init__(self, **data):
        super().__init__(**data)

    # Validate the function
    @validator("code")
    def validate_func(cls, v):
        try:
            validate.eval_function(v)
        except Exception as e:
            raise e

        return v

    def get_function(self):
        """Get the function"""
        function_name = validate.extract_function_name(self.code)

        return validate.create_function(self.code, function_name)


class PythonFunctionTool(Function, Tool):
    name: str = "Custom Tool"
    description: str
    code: str

    def ___init__(self, name: str, description: str, code: str):
        self.name = name
        self.description = description
        self.code = code
        self.func = get_function(self.code)
        super().__init__(name=name, description=description, func=self.func)


class PythonFunction(Function):
    code: str


class CustomComponent_old(BaseModel):
    code: str
    function: Optional[Callable] = None
    imports: Optional[str] = None

    # Eval code and store the class
    def __init__(self, **data):
        super().__init__(**data)

    # Validate the Class code
    @validator("code")
    def validate_func(cls, v):
        try:
            validate.eval_function(v)
        except Exception as e:
            raise e

        return v

    def get_function(self):
        """Get the function"""
        function_name = validate.extract_function_name(self.code)

        return validate.create_function(self.code, function_name)


class CustomComponent(BaseModel):
    code: str
    function: Optional[Callable] = None
    function_entrypoint_name = "build"
    return_type_valid_list = [
        "ConversationChain",
        "Tool"
    ]
    class_template = {
        "imports": [],
        "class": {
            "inherited_classes": "",
            "name": "",
            "init": ""
        },
        "functions": []
    }

    def __init__(self, **data):
        super().__init__(**data)

    def _handle_import(self, node):
        for alias in node.names:
            module_name = getattr(node, 'module', None)
            self.class_template['imports'].append(
                f"{module_name}.{alias.name}" if module_name else alias.name)

    def _handle_class(self, node):
        self.class_template['class'].update({
            'name': node.name,
            'inherited_classes': [ast.unparse(base) for base in node.bases]
        })

        for inner_node in node.body:
            if isinstance(inner_node, ast.FunctionDef):
                self._handle_function(inner_node)

    def _handle_function(self, node):
        function_name = node.name
        function_args_str = ast.unparse(node.args)
        function_args = function_args_str.split(
            ", ") if function_args_str else []

        return_type = ast.unparse(node.returns) if node.returns else "None"

        function_data = {
            "name": function_name,
            "arguments": function_args,
            "return_type": return_type
        }

        if function_name == "__init__":
            self.class_template['class']['init'] = function_args_str.split(
                ", ") if function_args_str else []
        else:
            self.class_template["functions"].append(function_data)

    def transform_list(self, input_list):
        output_list = []
        for item in input_list:
            # Split each item on ':' to separate variable name and type
            split_item = item.split(':')

            # If there is a type, strip any leading/trailing spaces from it
            if len(split_item) > 1:
                split_item[1] = split_item[1].strip()
            # If there isn't a type, append None
            else:
                split_item.append(None)
            output_list.append(split_item)

        return output_list

    def extract_class_info(self):
        module = ast.parse(self.code)

        for node in module.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                self._handle_import(node)
            elif isinstance(node, ast.ClassDef):
                self._handle_class(node)

        return self.class_template

    def get_entrypoint_function_args_and_return_type(self):
        data = self.extract_class_info()
        functions = data.get("functions", [])

        if build_function := next(
            (f for f in functions if f["name"]
             == self.function_entrypoint_name),
            None,
        ):
            function_args = build_function.get("arguments", None)
            function_args = self.transform_list(function_args)

            return_type = build_function.get("return_type", None)
        else:
            function_args = None
            return_type = None

        return function_args, return_type

    def is_valid_class_template(self, code: dict):
        class_name = code.get("class", {}).get("name", None)
        if not class_name:  # this will also check for None, empty string, etc.
            return False

        functions = code.get("functions", [])
        if build_function := next(
            (f for f in functions if f["name"]
             == self.function_entrypoint_name),
            None,
        ):
            # Check if the return type of the build function is valid
            return build_function.get("return_type") in self.return_type_valid_list
        else:
            return False

    def get_function(self):
        return validate.create_function(
            self.code,
            self.function_entrypoint_name
        )

    @property
    def data(self):
        return self.extract_class_info()

    @property
    def is_valid(self):
        return self.is_valid_class_template(self.data)

    @property
    def args_and_return_type(self):
        return self.get_entrypoint_function_args_and_return_type()

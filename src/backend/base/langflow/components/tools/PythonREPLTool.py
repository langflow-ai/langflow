import importlib
from typing import List, Union
from pydantic import BaseModel, Field
from langflow.base.langchain_utilities.model import LCToolComponent
from langflow.inputs import StrInput
from langflow.schema import Data
from langflow.field_typing import Tool
from langchain.tools import StructuredTool
from langchain_experimental.utilities import PythonREPL


class PythonREPLToolComponent(LCToolComponent):
    display_name = "Python REPL Tool"
    description = "A tool for running Python code in a REPL environment."
    name = "PythonREPLTool"

    inputs = [
        StrInput(
            name="name",
            display_name="Tool Name",
            info="The name of the tool.",
            value="python_repl",
        ),
        StrInput(
            name="description",
            display_name="Tool Description",
            info="A description of the tool.",
            value="A Python shell. Use this to execute python commands. Input should be a valid python command. If you want to see the output of a value, you should print it out with `print(...)`.",
        ),
        StrInput(
            name="global_imports",
            display_name="Global Imports",
            info="A comma-separated list of modules to import globally, e.g. 'math,numpy'.",
            value="math",
        ),
        StrInput(
            name="code",
            display_name="Python Code",
            info="The Python code to execute.",
            value="print('Hello, World!')",
        ),
    ]

    class PythonREPLSchema(BaseModel):
        code: str = Field(..., description="The Python code to execute.")

    def get_globals(self, global_imports: Union[str, List[str]]) -> dict:
        global_dict = {}
        if isinstance(global_imports, str):
            modules = [module.strip() for module in global_imports.split(",")]
        elif isinstance(global_imports, list):
            modules = global_imports
        else:
            raise ValueError("global_imports must be either a string or a list")

        for module in modules:
            try:
                imported_module = importlib.import_module(module)
                global_dict[imported_module.__name__] = imported_module
            except ImportError:
                raise ImportError(f"Could not import module {module}")
        return global_dict

    def build_tool(self) -> Tool:
        _globals = self.get_globals(self.global_imports)
        python_repl = PythonREPL(_globals=_globals)

        def run_python_code(code: str) -> str:
            try:
                return python_repl.run(code)
            except Exception as e:
                return f"Error: {str(e)}"

        tool = StructuredTool.from_function(
            name=self.name,
            description=self.description,
            func=run_python_code,
            args_schema=self.PythonREPLSchema,
        )

        self.status = f"Python REPL Tool created with global imports: {self.global_imports}"
        return tool

    def run_model(self) -> List[Data]:
        tool = self.build_tool()
        result = tool.run(self.code)
        return [Data(data={"result": result})]

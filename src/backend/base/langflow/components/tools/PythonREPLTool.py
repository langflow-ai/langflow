import importlib
from typing import cast

from langchain_experimental.utilities import PythonREPL

from langflow.base.langchain_utilities.model import LCToolComponent
from langflow.field_typing import Tool
from langflow.io import MessageTextInput, MultiselectInput
from langflow.schema.data import Data
from langflow.template.field.base import Output


class PythonREPLToolComponent(LCToolComponent):
    display_name = "Python REPL Tool"
    description = "A tool for running Python code in a REPL environment."
    name = "PythonREPLTool"

    inputs = [
        MessageTextInput(name="input_value", display_name="Input", value=""),
        MessageTextInput(name="name", display_name="Name", value="python_repl"),
        MessageTextInput(
            name="description",
            display_name="Description",
            value="A Python shell. Use this to execute python commands. Input should be a valid python command. If you want to see the output of a value, you should print it out with `print(...)`.",
        ),
        MultiselectInput(
            name="global_imports",
            display_name="Global Imports",
            info="A list of modules to import globally, e.g. ['math', 'numpy'].",
            value=["math"],
            combobox=True,
        ),
    ]

    outputs = [
        Output(name="api_run_model", display_name="Data", method="run_model"),
        # Keep this for backwards compatibility
        Output(name="tool", display_name="Tool", method="build_tool"),
    ]

    def get_globals(self, globals: list[str]) -> dict:
        """
        Retrieves the global variables from the specified modules.

        Args:
            globals (list[str]): A list of module names.

        Returns:
            dict: A dictionary containing the global variables from the specified modules.
        """
        global_dict = {}
        for module in globals:
            try:
                imported_module = importlib.import_module(module)
                global_dict[imported_module.__name__] = imported_module
            except ImportError:
                raise ImportError(f"Could not import module {module}")
        return global_dict

    def build_tool(self) -> Tool:
        """
        Builds a Python REPL tool.

        Returns:
            Tool: The built Python REPL tool.
        """
        _globals = self.get_globals(self.global_imports)
        python_repl = PythonREPL(_globals=_globals)
        return cast(
            Tool,
            Tool(
                name=self.name,
                description=self.description,
                func=python_repl.run,
            ),
        )

    def run_model(self) -> Data:
        tool = self.build_tool()
        result = tool.invoke(self.input_value)
        return Data(text=result)

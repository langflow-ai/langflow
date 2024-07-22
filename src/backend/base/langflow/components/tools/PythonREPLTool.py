import importlib
from langchain_experimental.utilities import PythonREPL

from langflow.base.tools.base import build_status_from_tool
from langflow.custom import CustomComponent
from langchain_core.tools import Tool


class PythonREPLToolComponent(CustomComponent):
    display_name = "Python REPL Tool"
    description = "A tool for running Python code in a REPL environment."
    name = "PythonREPLTool"

    def build_config(self):
        return {
            "name": {"display_name": "Name", "info": "The name of the tool."},
            "description": {"display_name": "Description", "info": "A description of the tool."},
            "global_imports": {
                "display_name": "Global Imports",
                "info": "A list of modules to import globally, e.g. ['math', 'numpy'].",
            },
        }

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

    def build(
        self,
        name: str = "python_repl",
        description: str = "A Python shell. Use this to execute python commands. Input should be a valid python command. If you want to see the output of a value, you should print it out with `print(...)`.",
        global_imports: list[str] = ["math"],
    ) -> Tool:
        """
        Builds a Python REPL tool.

        Args:
            name (str, optional): The name of the tool. Defaults to "python_repl".
            description (str, optional): The description of the tool. Defaults to "A Python shell. Use this to execute python commands. Input should be a valid python command. If you want to see the output of a value, you should print it out with `print(...)`. ".
            global_imports (list[str], optional): A list of global imports to be available in the Python REPL. Defaults to ["math"].

        Returns:
            Tool: The built Python REPL tool.
        """
        _globals = self.get_globals(global_imports)
        python_repl = PythonREPL(_globals=_globals)
        tool = Tool(
            name=name,
            description=description,
            func=python_repl.run,
        )
        self.status = build_status_from_tool(tool)
        return tool

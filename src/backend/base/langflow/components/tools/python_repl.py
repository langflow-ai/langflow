import ast
import importlib

from langchain_experimental.utilities import PythonREPL

from langflow.custom import Component
from langflow.io import CodeInput, Output
from langflow.schema import Data


class PythonREPLToolComponent(Component):
    display_name = "Python REPL"
    description = "A tool for running Python code in a REPL environment with dynamic imports."
    icon = "Python"
    name = "PythonREPL"

    inputs = [
        CodeInput(
            name="python_code",
            display_name="Python Code",
            info="The Python code to execute. Supports both 'import' and 'from import' statements.",
            value="print('Hello, World!')",
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(
            display_name="Results",
            name="results",
            type_=Data,
            method="run_python_repl",
        ),
    ]

    def extract_imports_and_names(self, code: str) -> tuple[set[str], dict[str, set[str]]]:
        """Extract both regular imports and from-imports from the code.

        Returns a tuple of (regular_imports, from_imports) where from_imports is a dict
        mapping module names to sets of imported names.
        """
        try:
            tree = ast.parse(code)
            regular_imports: set[str] = set()
            from_imports: dict[str, set[str]] = {}

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        regular_imports.add(alias.name.split(".")[0])
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        module_name = node.module.split(".")[0]
                        if module_name not in from_imports:
                            from_imports[module_name] = set()
                        for alias in node.names:
                            from_imports[module_name].add(alias.name)
                elif isinstance(node, ast.Name):
                    regular_imports.add(node.id)
        except SyntaxError:
            self.log("Syntax error in code, could not extract imports and names")
            return set(), {}
        else:
            return regular_imports, from_imports

    def get_globals(self, regular_imports: set[str], from_imports: dict[str, set[str]]) -> dict:
        """Create a globals dictionary containing both regular imports and specific imports from modules."""
        global_dict = {}

        # Handle regular imports
        for name in regular_imports:
            try:
                module = importlib.import_module(name)
                global_dict[name] = module
            except ImportError:
                # If it's not a module, it might be a built-in or a name defined in the code
                pass

        # Handle from-imports
        for module_name, names in from_imports.items():
            try:
                module = importlib.import_module(module_name)
                for name in names:
                    try:
                        # Get the specific attribute from the module
                        attr = getattr(module, name)
                        global_dict[name] = attr
                    except AttributeError:
                        self.log(f"Could not import {name} from module {module_name}")
            except ImportError:
                self.log(f"Could not import module {module_name}")

        return global_dict

    def run_python_repl(self) -> Data:
        try:
            # Extract both types of imports
            regular_imports, from_imports = self.extract_imports_and_names(self.python_code)

            # Get global dictionary with all imported items
            globals_ = self.get_globals(regular_imports, from_imports)

            # Create PythonREPL with the global dictionary
            python_repl = PythonREPL(_globals=globals_)

            # Run the code
            result = python_repl.run(self.python_code)

            # Remove any trailing newlines and whitespace
            result = result.strip() if result else ""

            return Data(data={"result": result})
        except (ImportError, SyntaxError, NameError, TypeError, ValueError) as e:
            self.log(f"Error running Python code: {e!s}")
            error_message = str(e)
            return Data(data={"error": error_message})

    def build(self):
        return self.run_python_repl

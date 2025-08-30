import importlib
import os
import sys
from io import StringIO

from langflow.custom.custom_component.component import Component
from langflow.io import CodeInput, Output, StrInput
from langflow.schema.data import Data


class PythonREPLComponent(Component):
    display_name = "Python Interpreter"
    description = "Run Python code with optional imports. Use print() to see the output."
    documentation: str = "https://docs.langflow.org/components-processing#python-interpreter"
    icon = "square-terminal"

    inputs = [
        StrInput(
            name="global_imports",
            display_name="Global Imports",
            info="A comma-separated list of modules to import globally, e.g. 'math,numpy,pandas'.",
            value="math,pandas",
            required=True,
        ),
        CodeInput(
            name="python_code",
            display_name="Python Code",
            info="The Python code to execute. Only modules specified in Global Imports can be used.",
            value="print('Hello, World!')",
            input_types=["Message"],
            tool_mode=True,
            required=True,
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

    def get_globals(self, global_imports: str | list[str]) -> dict:
        """Create a globals dictionary with only the specified allowed imports."""
        global_dict = {}

        try:
            if isinstance(global_imports, str):
                modules = [module.strip() for module in global_imports.split(",")]
            elif isinstance(global_imports, list):
                modules = global_imports
            else:
                msg = "global_imports must be either a string or a list"
                raise TypeError(msg)

            for module in modules:
                try:
                    imported_module = importlib.import_module(module)
                    global_dict[imported_module.__name__] = imported_module
                except ImportError as e:
                    msg = f"Could not import module {module}: {e!s}"
                    raise ImportError(msg) from e

        except Exception as e:
            self.log(f"Error in global imports: {e!s}")
            raise
        else:
            self.log(f"Successfully imported modules: {list(global_dict.keys())}")
            return global_dict

    def _is_sandboxed(self) -> bool:
        """Check if we're running inside a sandbox environment."""
        # Check for sandbox-specific environment variables
        return any([
            os.environ.get("LANGFLOW_EXECUTION_ID"),  # Set by sandbox executor
            os.environ.get("LANGFLOW_USE_STDIN"),      # Set by sandbox executor
            "/opt/executor.py" in sys.argv[0] if sys.argv else False,  # Running as executor
        ])

    def run_python_repl(self) -> Data:
        try:
            # Get the globals dictionary with allowed imports
            globals_ = self.get_globals(self.global_imports)

            # Check if we're in a sandbox environment
            if self._is_sandboxed():
                # Use simple exec-based implementation for sandbox
                self.log("Running in sandbox mode - using exec-based implementation")
                return self._run_with_exec(globals_)
            # Use langchain's PythonREPL for non-sandbox (supports multiprocessing)
            self.log("Running in standard mode - using langchain PythonREPL")
            return self._run_with_langchain_repl(globals_)

        except ImportError as e:
            error_message = f"Import Error: {e!s}"
            self.log(error_message)
            return Data(data={"error": error_message})

        except SyntaxError as e:
            error_message = f"Syntax Error: {e!s}"
            self.log(error_message)
            return Data(data={"error": error_message})

        except (NameError, TypeError, ValueError) as e:
            error_message = f"Error during execution: {e!s}"
            self.log(error_message)
            return Data(data={"error": error_message})

        except Exception as e:
            error_message = f"Execution error: {e!s}"
            self.log(error_message)
            return Data(data={"error": error_message})

    def _run_with_exec(self, globals_: dict) -> Data:
        """Run Python code using exec (sandbox-compatible)."""
        # Capture stdout
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()

        try:
            # Execute the code with the restricted globals
            # Note: This runs in the same process, no multiprocessing needed
            exec(self.python_code, globals_)

            # Get the captured output
            result = captured_output.getvalue()
            result = result.strip() if result else ""

            return Data(data={"result": result})

        finally:
            # Always restore stdout
            sys.stdout = old_stdout

    def _run_with_langchain_repl(self, globals_: dict) -> Data:
        """Run Python code using langchain's PythonREPL (supports multiprocessing)."""
        try:
            from langchain_experimental.utilities import PythonREPL
        except ImportError:
            # Fallback to exec if langchain_experimental is not available
            return self._run_with_exec(globals_)

        python_repl = PythonREPL(_globals=globals_)
        result = python_repl.run(self.python_code)
        result = result.strip() if result else ""

        return Data(data={"result": result})

    def build(self):
        return self.run_python_repl

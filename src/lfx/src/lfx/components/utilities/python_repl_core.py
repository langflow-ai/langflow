import importlib

from lfx.custom.custom_component.component import Component
from lfx.io import MultilineInput, Output, StrInput
from lfx.schema.data import Data
from lfx.utils.python_repl_security import ensure_code_execution_enabled, safe_builtins, validate_code_safety


class PythonREPLComponent(Component):
    display_name = "Python Interpreter"
    description = "Run Python code with optional imports. Use print() to see the output."
    documentation: str = "https://docs.langflow.org/python-interpreter"
    icon = "square-terminal"

    inputs = [
        StrInput(
            name="global_imports",
            display_name="Global Imports",
            info="A comma-separated list of modules to import globally, e.g. 'math,numpy,pandas'.",
            # Default kept minimal: powerful modules (e.g. pandas, whose read_pickle/eval
            # are code-execution sinks) must be opted into explicitly via this field.
            value="math",
            required=True,
        ),
        MultilineInput(
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
            # Restrict builtins so the import allow-list cannot be silently bypassed
            # (e.g. __import__("subprocess")). Without this, exec() auto-injects the full
            # builtins module, leaving __import__/open/eval/exec reachable.
            global_dict["__builtins__"] = safe_builtins()
            return global_dict

    def run_python_repl(self) -> Data:
        try:
            # Refuse to run user code when allow_custom_components is disabled
            # (GHSA-8qpj-27x8-pwpq). Raised before any sanitize/exec.
            ensure_code_execution_enabled()
            # Validate the exact code that will run: PythonREPL.run() strips a leading
            # "python"/backticks/whitespace prefix before exec, so validate the sanitized
            # form. Rejects inline imports and escape gadgets (e.g.
            # ().__class__.__subclasses__()); combined with restricted builtins in get_globals().
            from langchain_experimental.utilities import PythonREPL

            code = PythonREPL.sanitize_input(self.python_code)
            validate_code_safety(code)
            globals_ = self.get_globals(self.global_imports)
            python_repl = PythonREPL(_globals=globals_)
            result = python_repl.run(code)
            result = result.strip() if result else ""

            self.log("Code execution completed successfully")
            return Data(data={"result": result})

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

    def build(self):
        return self.run_python_repl

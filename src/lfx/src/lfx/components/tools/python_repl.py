import importlib

from langchain_core.tools import StructuredTool, ToolException
from pydantic import BaseModel, Field

from lfx.base.langchain_utilities.model import LCToolComponent
from lfx.field_typing import Tool
from lfx.inputs.inputs import StrInput
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.utils.python_repl_security import ensure_code_execution_enabled, safe_builtins, validate_code_safety
from lfx.utils.sandbox import is_sandbox_enabled, run_code_in_sandbox, sanitize_code


class PythonREPLToolComponent(LCToolComponent):
    display_name = "Python REPL"
    description = "A tool for running Python code in a REPL environment."
    name = "PythonREPLTool"
    icon = "Python"
    legacy = True
    replacement = ["processing.PythonREPLComponent"]

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
            value="A Python shell. Use this to execute python commands. "
            "Input should be a valid python command. "
            "If you want to see the output of a value, you should print it out with `print(...)`.",
        ),
        StrInput(
            name="global_imports",
            display_name="Global Imports",
            info="A comma-separated list of modules to import globally, e.g. 'math,numpy'.",
            value="math",
        ),
        StrInput(
            name="python_code",
            display_name="Python Code",
            info="The Python code to execute.",
            value="print('Hello, World!')",
        ),
    ]

    @staticmethod
    def _normalize_legacy_code_input(params: dict) -> dict:
        # `code` is reserved for the component's source. Preserve programmatic
        # callers that used the old input name while serializing the value separately.
        if "code" in params:
            params.setdefault("python_code", params.pop("code"))
        return params

    def set(self, **kwargs):
        return super().set(**self._normalize_legacy_code_input(kwargs))

    def set_attributes(self, params: dict) -> None:
        super().set_attributes(self._normalize_legacy_code_input(params))

    def set_input_value(self, name: str, value) -> None:
        super().set_input_value("python_code" if name == "code" else name, value)

    class PythonREPLSchema(BaseModel):
        code: str = Field(..., description="The Python code to execute.")

    def get_globals(self, global_imports: str | list[str]) -> dict:
        global_dict = {}
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
                msg = f"Could not import module {module}"
                raise ImportError(msg) from e
        # Restrict builtins so the import allow-list cannot be silently bypassed
        # (e.g. __import__("subprocess")). Without this, exec() auto-injects the full
        # builtins module, leaving __import__/open/eval/exec reachable.
        global_dict["__builtins__"] = safe_builtins()
        return global_dict

    def _get_input_value(self, key: str) -> str | None:
        """Return the value of the input named ``key``, ignoring shadowing class attributes."""
        value = self._attributes.get(key)
        if not value and key in self._inputs:
            value = self._inputs[key].value
        if value is None or isinstance(value, str):
            return value
        # StrInput only warns on non-string values, so a non-string can reach here;
        # StructuredTool.from_function requires string metadata (it strips the
        # description), so coerce instead of crashing deep inside langchain-core.
        return str(value)

    def build_tool(self) -> Tool:
        def run_python_code(code: str) -> str:
            try:
                # Refuse to run user code when allow_custom_components is disabled
                # (GHSA-8qpj-27x8-pwpq).
                ensure_code_execution_enabled()

                # Opt-in microVM isolation (LANGFLOW_SANDBOX_BACKEND, issue
                # #12029): the VM boundary replaces the in-process import
                # allow-list / AST mitigations below. Sandbox errors
                # (including configured-but-unavailable) surface as
                # ToolException — never fall back to in-process exec.
                if is_sandbox_enabled():
                    result = run_code_in_sandbox(sanitize_code(code), global_imports=self.global_imports)
                    if not result.success:
                        # Parity with the in-process path: PythonREPL.run()
                        # RETURNS user-code errors as the observation string
                        # (so agents can read the traceback and self-correct)
                        # rather than raising. Only sandbox infrastructure
                        # errors raise (via run_code_in_sandbox above).
                        return result.error_message()
                    return result.stdout
                # Validate the exact (sanitized) code that will run, rejecting inline
                # imports and escape gadgets; combined with the restricted builtins in
                # get_globals(). A fresh globals namespace is built per invocation so
                # state does not leak across tool calls.
                from langchain_experimental.utilities import PythonREPL

                cleaned_code = PythonREPL.sanitize_input(code)
                validate_code_safety(cleaned_code)
                python_repl = PythonREPL(_globals=self.get_globals(self.global_imports))
                return python_repl.run(cleaned_code)
            except Exception as e:
                logger.debug("Error running Python code", exc_info=True)
                raise ToolException(str(e)) from e

        # The StrInputs named "name" and "description" are shadowed by this class's
        # own `name`/`description` attributes — Component.__getattr__ only fires when
        # normal lookup fails, so self.name/self.description always resolve to the
        # class attributes. Read the input values explicitly, keeping the class
        # attributes as fallback when the inputs are empty.
        tool_name = self._get_input_value("name") or type(self).name
        tool_description = self._get_input_value("description") or type(self).description

        tool = StructuredTool.from_function(
            name=tool_name,
            description=tool_description,
            func=run_python_code,
            args_schema=self.PythonREPLSchema,
        )

        self.status = f"Python REPL Tool created with global imports: {self.global_imports}"
        return tool

    def run_model(self) -> list[Data]:
        tool = self.build_tool()
        code_input = "" if self.python_code is None else self.python_code
        result = tool.run({"code": code_input})
        return [Data(data={"result": result})]

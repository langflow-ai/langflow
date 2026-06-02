import pytest
from langchain_core.tools import ToolException
from lfx.components.tools.python_repl import PythonREPLToolComponent
from lfx.components.utilities.python_repl_core import PythonREPLComponent

from tests.base import DID_NOT_EXIST, ComponentTestBaseWithoutClient


class TestPythonREPLComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return PythonREPLComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "global_imports": "math",
            "python_code": "print('Hello, World!')",
        }

    @pytest.fixture
    def file_names_mapping(self):
        # Component not yet released, mark all versions as non-existent
        return [
            {"version": "1.0.17", "module": "tools", "file_name": DID_NOT_EXIST},
            {"version": "1.0.18", "module": "tools", "file_name": DID_NOT_EXIST},
            {"version": "1.0.19", "module": "tools", "file_name": DID_NOT_EXIST},
            {"version": "1.1.0", "module": "tools", "file_name": DID_NOT_EXIST},
            {"version": "1.1.1", "module": "tools", "file_name": DID_NOT_EXIST},
        ]

    def test_component_initialization(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        frontend_node = component.to_frontend_node()
        node_data = frontend_node["data"]["node"]

        # Test template fields
        template = node_data["template"]
        assert "global_imports" in template
        assert "python_code" in template

        # Test global_imports configuration
        global_imports = template["global_imports"]
        assert global_imports["type"] == "str"
        assert global_imports["value"] == "math"
        assert global_imports["required"] is True

        # Test python_code configuration
        python_code = template["python_code"]
        # assert python_code["type"] == "code"  # TODO: Restore when CodeInput is included in component
        assert python_code["type"] == "str"  # TODO: Remove when CodeInput is included in component
        assert python_code["value"] == "print('Hello, World!')"
        assert python_code["required"] is True

        # Test base configuration - JSON is the new name (Data is alias for backward compatibility)
        assert "JSON" in node_data["base_classes"]


class TestPythonREPLComponentSecurity:
    """Regression tests for the __builtins__ sandbox-bypass RCE in the Python Interpreter.

    The Global Imports allow-list must not be silently bypassable: dangerous builtins
    (__import__, open, eval, ...) and the builtin-free escape gadgets must be blocked,
    while ordinary code keeps working.
    """

    def _run(self, code, global_imports="math"):
        return PythonREPLComponent(global_imports=global_imports, python_code=code).run_python_repl().data

    def test_legitimate_code_still_runs(self):
        """The default example (and print()) must keep working after restricting builtins."""
        assert self._run("print('Hello, World!')").get("result") == "Hello, World!"

    def test_whitelisted_module_works(self):
        """A module from Global Imports remains usable."""
        assert "4.0" in self._run("print(math.sqrt(16))").get("result", "")

    def test_import_builtin_is_blocked(self):
        """__import__ is not in the restricted builtins, so the headline RCE payload fails."""
        rendered = str(self._run('print(__import__("subprocess").check_output(["echo", "PWNED"]))'))
        assert "PWNED" not in rendered
        assert "NameError" in rendered

    def test_open_builtin_is_blocked(self):
        """Filesystem access via open() is blocked."""
        rendered = str(self._run('print(open("/etc/passwd").read())'))
        assert "root:" not in rendered
        assert "NameError" in rendered

    def test_eval_builtin_is_blocked(self):
        """eval() is not exposed."""
        assert "NameError" in str(self._run('print(eval("1+1"))'))

    def test_subclasses_escape_is_blocked(self):
        """The classic builtin-free escape gadget is rejected before execution."""
        data = self._run("print(().__class__.__bases__[0].__subclasses__())")
        assert "error" in data
        assert "not allowed" in data["error"]

    def test_inline_import_is_blocked(self):
        """Inline imports are rejected; modules must come from the Global Imports field."""
        data = self._run("import os\nprint(os.getcwd())")
        assert "error" in data
        assert "not allowed" in data["error"]

    def test_format_string_dunder_escape_is_blocked(self):
        """str.format() dunder traversal (invisible to the AST attr check) is rejected."""
        data = self._run('f = lambda: 0\nprint("{0.__globals__}".format(f))')
        assert "error" in data
        assert "not allowed" in data["error"]

    def test_default_global_imports_excludes_pandas(self):
        """The default allow-list is minimal (no pandas) to avoid bundling a deserialization sink."""
        template = PythonREPLComponent().to_frontend_node()["data"]["node"]["template"]
        assert template["global_imports"]["value"] == "math"


class TestPythonREPLToolComponentSecurity:
    """The same hardening applies to the legacy Python REPL *tool* component."""

    def _func(self, global_imports="math"):
        component = PythonREPLToolComponent(
            name="python_repl",
            description="run code",
            global_imports=global_imports,
            code="print('x')",
        )
        return component.build_tool().func

    def test_tool_runs_legitimate_code(self):
        assert "hi" in self._func()("print('hi')")

    def test_tool_blocks_inline_import(self):
        with pytest.raises(ToolException, match="not allowed"):
            self._func()("import os")

    def test_tool_blocks_subclasses_escape(self):
        with pytest.raises(ToolException, match="not allowed"):
            self._func()("().__class__.__bases__[0].__subclasses__()")

    def test_tool_blocks_import_builtin(self):
        """__import__ is a bare name; PythonREPL surfaces the NameError as a string."""
        result = self._func()('__import__("subprocess").check_output(["echo", "PWNED"])')
        assert "PWNED" not in result
        assert "NameError" in result

    def test_tool_invocations_do_not_share_state(self):
        """Each tool call gets a fresh namespace, so variables do not leak across calls."""
        func = self._func()
        func("leaked = 12345")
        result = func("print(leaked)")
        assert "NameError" in result

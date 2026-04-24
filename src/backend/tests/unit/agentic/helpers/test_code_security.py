"""Tests for code security scanning.

Tests cover:
- Safe component code that should pass
- Dangerous function calls (exec, eval, os.system, subprocess, etc.)
- Dangerous imports
- Edge cases (syntax errors, empty code)
"""

from langflow.agentic.helpers.code_security import scan_code_security


class TestScanCodeSecuritySafeCode:
    """Tests that safe component code passes the security scan."""

    def test_should_pass_basic_component(self):
        """Basic Langflow component should pass."""
        code = """
from lfx.custom import Component
from lfx.io import MessageTextInput, Output
from lfx.schema import Data

class MyComponent(Component):
    display_name = "My Component"
    inputs = [MessageTextInput(name="text", display_name="Text")]
    outputs = [Output(name="result", display_name="Result", method="build")]

    def build(self) -> Data:
        return Data(data={"text": self.text})
"""
        result = scan_code_security(code)
        assert result.is_safe is True
        assert result.violations == ()

    def test_should_pass_os_path_usage(self):
        """os.path operations are safe and should pass."""
        code = """
import os
path = os.path.join("a", "b")
exists = os.path.exists(path)
"""
        result = scan_code_security(code)
        assert result.is_safe is True

    def test_should_pass_http_requests(self):
        """Standard HTTP requests library should pass."""
        code = """
import requests
response = requests.get("https://api.example.com/data")
"""
        result = scan_code_security(code)
        assert result.is_safe is True

    def test_should_pass_json_operations(self):
        """JSON operations should pass."""
        code = """
import json
data = json.loads('{"key": "value"}')
result = json.dumps(data)
"""
        result = scan_code_security(code)
        assert result.is_safe is True

    def test_should_pass_math_operations(self):
        """Math operations should pass."""
        code = """
import math
result = math.sqrt(16)
"""
        result = scan_code_security(code)
        assert result.is_safe is True


class TestScanCodeSecurityDangerousCalls:
    """Tests that dangerous function calls are detected."""

    def test_should_detect_exec(self):
        """exec() call should be detected."""
        code = 'exec("print(1)")'
        result = scan_code_security(code)
        assert result.is_safe is False
        assert any("exec()" in v for v in result.violations)

    def test_should_detect_eval(self):
        """eval() call should be detected."""
        code = 'result = eval("1+1")'
        result = scan_code_security(code)
        assert result.is_safe is False
        assert any("eval()" in v for v in result.violations)

    def test_should_detect_compile(self):
        """compile() call should be detected."""
        code = 'code = compile("print(1)", "<string>", "exec")'
        result = scan_code_security(code)
        assert result.is_safe is False
        assert any("compile()" in v for v in result.violations)

    def test_should_detect_dunder_import(self):
        """__import__() call should be detected."""
        code = 'mod = __import__("os")'
        result = scan_code_security(code)
        assert result.is_safe is False
        assert any("__import__()" in v for v in result.violations)

    def test_should_detect_globals(self):
        """globals() call should be detected."""
        code = "g = globals()"
        result = scan_code_security(code)
        assert result.is_safe is False
        assert any("globals()" in v for v in result.violations)


class TestScanCodeSecurityDangerousAttrCalls:
    """Tests that dangerous attribute calls (module.method) are detected."""

    def test_should_detect_os_system(self):
        """os.system() should be detected."""
        code = 'import os\nos.system("rm -rf /")'
        result = scan_code_security(code)
        assert result.is_safe is False
        assert any("os.system()" in v for v in result.violations)

    def test_should_detect_os_popen(self):
        """os.popen() should be detected."""
        code = 'import os\nos.popen("ls")'
        result = scan_code_security(code)
        assert result.is_safe is False
        assert any("os.popen()" in v for v in result.violations)

    def test_should_detect_os_remove(self):
        """os.remove() should be detected."""
        code = 'import os\nos.remove("/tmp/file")'
        result = scan_code_security(code)
        assert result.is_safe is False

    def test_should_detect_subprocess_run(self):
        """subprocess.run() should be detected."""
        code = 'import subprocess\nsubprocess.run(["ls"])'
        result = scan_code_security(code)
        assert result.is_safe is False

    def test_should_detect_subprocess_popen(self):
        """subprocess.Popen() should be detected."""
        code = 'import subprocess\nsubprocess.Popen(["ls"])'
        result = scan_code_security(code)
        assert result.is_safe is False

    def test_should_detect_shutil_rmtree(self):
        """shutil.rmtree() should be detected."""
        code = 'import shutil\nshutil.rmtree("/tmp")'
        result = scan_code_security(code)
        assert result.is_safe is False

    def test_should_detect_sys_exit(self):
        """sys.exit() should be detected."""
        code = "import sys\nsys.exit(1)"
        result = scan_code_security(code)
        assert result.is_safe is False


class TestScanCodeSecurityDangerousImports:
    """Tests that dangerous imports are detected."""

    def test_should_detect_subprocess_import(self):
        """Import subprocess should be detected."""
        code = "import subprocess"
        result = scan_code_security(code)
        assert result.is_safe is False
        assert any("subprocess" in v for v in result.violations)

    def test_should_detect_shutil_import(self):
        """Import shutil should be detected."""
        code = "import shutil"
        result = scan_code_security(code)
        assert result.is_safe is False

    def test_should_detect_pickle_import(self):
        """Import pickle should be detected."""
        code = "import pickle"
        result = scan_code_security(code)
        assert result.is_safe is False

    def test_should_detect_ctypes_import(self):
        """Import ctypes should be detected."""
        code = "import ctypes"
        result = scan_code_security(code)
        assert result.is_safe is False

    def test_should_detect_from_subprocess_import(self):
        """From subprocess import run should be detected."""
        code = "from subprocess import run"
        result = scan_code_security(code)
        assert result.is_safe is False

    def test_should_detect_restricted_os_import(self):
        """From os import system should be detected."""
        code = "from os import system"
        result = scan_code_security(code)
        assert result.is_safe is False

    def test_should_allow_os_path_import(self):
        """From os import path should be allowed."""
        code = "from os import path"
        result = scan_code_security(code)
        assert result.is_safe is True

    def test_should_allow_os_import_itself(self):
        """Import os alone should pass (specific functions are blocked)."""
        code = "import os"
        result = scan_code_security(code)
        assert result.is_safe is True


class TestScanCodeSecurityMultipleViolations:
    """Tests detection of multiple violations in the same code."""

    def test_should_report_all_violations(self):
        """Should report all violations, not just the first one."""
        code = 'import subprocess\nexec("x")\neval("y")'
        result = scan_code_security(code)
        assert result.is_safe is False
        assert len(result.violations) >= 3

    def test_should_detect_import_and_call_violations(self):
        """Should detect both dangerous import and dangerous call."""
        code = 'import shutil\nos.system("cmd")'
        result = scan_code_security(code)
        assert result.is_safe is False
        assert len(result.violations) >= 2


class TestScanCodeSecurityEdgeCases:
    """Tests edge cases and boundary conditions."""

    def test_should_handle_syntax_error_gracefully(self):
        """Syntax errors should return is_safe=True (handled by validation.py)."""
        result = scan_code_security("def foo(:\n  pass")
        assert result.is_safe is True

    def test_should_handle_empty_code(self):
        """Empty code should return is_safe=True."""
        result = scan_code_security("")
        assert result.is_safe is True

    def test_should_handle_whitespace_only(self):
        """Whitespace-only code should return is_safe=True."""
        result = scan_code_security("   \n\n  ")
        assert result.is_safe is True

    def test_should_handle_none_like_empty(self):
        """Code with no dangerous patterns should pass."""
        result = scan_code_security("x = 1\ny = 2\nz = x + y")
        assert result.is_safe is True

    def test_violations_is_tuple(self):
        """Violations should be a tuple (immutable)."""
        result = scan_code_security("exec('x')")
        assert isinstance(result.violations, tuple)

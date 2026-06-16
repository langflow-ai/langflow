"""Unit tests for the Python REPL hardening helpers."""

import pytest
from lfx.utils.python_repl_security import safe_builtins, validate_code_safety


class TestSafeBuiltins:
    def test_excludes_dangerous_builtins(self):
        """Code-execution, import, filesystem and introspection builtins are removed."""
        builtins_map = safe_builtins()
        for name in (
            "__import__",
            "eval",
            "exec",
            "compile",
            "open",
            "input",
            "globals",
            "locals",
            "vars",
            "getattr",
            "setattr",
            "delattr",
            "breakpoint",
            "memoryview",
            "exit",
            "quit",
            "help",
        ):
            assert name not in builtins_map, f"{name} must not be exposed"

    def test_includes_common_safe_builtins(self):
        """Common, safe builtins remain available so normal code keeps working."""
        builtins_map = safe_builtins()
        for name in (
            "print",
            "len",
            "range",
            "int",
            "float",
            "str",
            "list",
            "dict",
            "tuple",
            "set",
            "sum",
            "min",
            "max",
            "sorted",
            "enumerate",
            "zip",
            "isinstance",
            "type",
            "Exception",
            "ValueError",
        ):
            assert name in builtins_map, f"{name} should be available"

    def test_returns_fresh_copy(self):
        """Each call returns an independent dict so callers cannot mutate shared state."""
        first = safe_builtins()
        first["injected"] = object()
        assert "injected" not in safe_builtins()


class TestValidateCodeSafety:
    @pytest.mark.parametrize(
        "code",
        [
            "import os",
            "import subprocess",
            "from os import system",
            "().__class__",
            "[].__class__.__bases__[0].__subclasses__()",
            "(lambda: 0).__globals__",
            "().__class__.__mro__",
            "(x for x in []).gi_frame",
            "object.__subclasses__()",
            'f"{().__class__}"',
            "int.mro()",
            '"{0.__globals__}".format(f)',
            '"{0[__builtins__]}".format(f)',
            '"{0.__class__}".format(obj)',
        ],
    )
    def test_blocks_escape_and_import(self, code):
        """Inline imports, dunder/frame escape gadgets, and format-string dunder access are rejected."""
        with pytest.raises(ValueError, match="not allowed"):
            validate_code_safety(code)

    @pytest.mark.parametrize(
        "code",
        [
            "print('Hello, World!')",
            "print(len([1, 2, 3]))",
            "x = 1\ny = x + 2\nprint(y)",
            "math.sqrt(16)",
            "result = [i * 2 for i in range(5)]\nprint(sum(result))",
            "data = {'a': 1, 'b': 2}\nprint(sorted(data.items()))",
            "'{0} and {1}'.format(1, 2)",
            "'{name}'.format(name='x')",
            "'{0:.2f}'.format(3.14159)",
        ],
    )
    def test_allows_safe_code(self, code):
        """Ordinary code (no imports, no dunder/frame access) is allowed."""
        validate_code_safety(code)  # should not raise

    def test_syntax_error_propagates(self):
        """Unparseable code surfaces a SyntaxError to the caller."""
        with pytest.raises(SyntaxError):
            validate_code_safety("print('unterminated")


class TestEnsureCodeExecutionEnabled:
    """GHSA-8qpj-27x8-pwpq: code execution honors allow_custom_components."""

    def test_blocks_when_custom_components_disabled(self, monkeypatch):
        from types import SimpleNamespace

        from lfx.utils.python_repl_security import CodeExecutionDisabledError, ensure_code_execution_enabled

        monkeypatch.setattr(
            "lfx.services.deps.get_settings_service",
            lambda: SimpleNamespace(settings=SimpleNamespace(allow_custom_components=False)),
        )
        with pytest.raises(CodeExecutionDisabledError):
            ensure_code_execution_enabled()

    def test_allows_when_custom_components_enabled(self, monkeypatch):
        from types import SimpleNamespace

        from lfx.utils.python_repl_security import ensure_code_execution_enabled

        monkeypatch.setattr(
            "lfx.services.deps.get_settings_service",
            lambda: SimpleNamespace(settings=SimpleNamespace(allow_custom_components=True)),
        )
        ensure_code_execution_enabled()  # must not raise

    def test_allows_when_settings_service_unavailable(self, monkeypatch):
        """Standalone lfx (no settings service) is local/trusted -> execution allowed."""
        from lfx.utils.python_repl_security import ensure_code_execution_enabled

        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: None)
        ensure_code_execution_enabled()  # must not raise

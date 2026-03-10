"""Tests for the code_sandbox module — security sandbox for custom component validation."""

import ast
from textwrap import dedent

import pytest

from lfx.custom.code_sandbox import (
    CodeSafetyError,
    _contains_call,
    create_restricted_builtins,
    filter_safe_definitions,
    sanitize_class_body,
    validate_code_safety,
)


# ---------------------------------------------------------------------------
# validate_code_safety — blocked imports
# ---------------------------------------------------------------------------


class TestBlockedImports:
    def test_blocks_subprocess_import(self):
        code = "import subprocess"
        with pytest.raises(CodeSafetyError, match="subprocess"):
            validate_code_safety(code)

    def test_blocks_subprocess_from_import(self):
        code = "from subprocess import check_output"
        with pytest.raises(CodeSafetyError, match="subprocess"):
            validate_code_safety(code)

    def test_blocks_socket_import(self):
        code = "import socket"
        with pytest.raises(CodeSafetyError, match="socket"):
            validate_code_safety(code)

    def test_blocks_pty_import(self):
        code = "import pty"
        with pytest.raises(CodeSafetyError, match="pty"):
            validate_code_safety(code)

    def test_blocks_ctypes_import(self):
        code = "import ctypes"
        with pytest.raises(CodeSafetyError, match="ctypes"):
            validate_code_safety(code)

    def test_blocks_shutil_import(self):
        code = "import shutil"
        with pytest.raises(CodeSafetyError, match="shutil"):
            validate_code_safety(code)

    def test_blocks_nested_blocked_module(self):
        code = "from http.server import HTTPServer"
        with pytest.raises(CodeSafetyError, match="http.server"):
            validate_code_safety(code)

    def test_allows_safe_imports(self):
        code = dedent("""\
            import os
            import json
            import re
            from pathlib import Path
            from typing import Optional
        """)
        # Should not raise
        validate_code_safety(code)

    def test_allows_langflow_imports(self):
        code = dedent("""\
            from langflow.custom import Component
            from langflow.io import Output
        """)
        validate_code_safety(code)


# ---------------------------------------------------------------------------
# validate_code_safety — dangerous builtin calls
# ---------------------------------------------------------------------------


class TestDangerousBuiltinCalls:
    def test_blocks_dunder_import_call(self):
        code = '__import__("os").system("id")'
        with pytest.raises(CodeSafetyError, match="__import__"):
            validate_code_safety(code)

    def test_blocks_exec_call(self):
        code = 'exec("print(1)")'
        with pytest.raises(CodeSafetyError, match="exec"):
            validate_code_safety(code)

    def test_blocks_eval_call(self):
        code = 'eval("1+1")'
        with pytest.raises(CodeSafetyError, match="eval"):
            validate_code_safety(code)

    def test_blocks_compile_call(self):
        code = 'compile("print(1)", "<string>", "exec")'
        with pytest.raises(CodeSafetyError, match="compile"):
            validate_code_safety(code)

    def test_allows_safe_function_calls(self):
        code = dedent("""\
            x = len([1, 2, 3])
            y = str(42)
            z = list(range(10))
        """)
        validate_code_safety(code)


# ---------------------------------------------------------------------------
# create_restricted_builtins
# ---------------------------------------------------------------------------


class TestRestrictedBuiltins:
    def test_removes_import(self):
        restricted = create_restricted_builtins()
        assert "__import__" not in restricted

    def test_removes_exec(self):
        restricted = create_restricted_builtins()
        assert "exec" not in restricted

    def test_removes_eval(self):
        restricted = create_restricted_builtins()
        assert "eval" not in restricted

    def test_removes_open(self):
        restricted = create_restricted_builtins()
        assert "open" not in restricted

    def test_removes_compile(self):
        restricted = create_restricted_builtins()
        assert "compile" not in restricted

    def test_keeps_safe_builtins(self):
        restricted = create_restricted_builtins()
        for name in ("len", "str", "int", "float", "list", "dict", "print", "range", "isinstance"):
            assert name in restricted, f"{name} should be in restricted builtins"


# ---------------------------------------------------------------------------
# filter_safe_definitions
# ---------------------------------------------------------------------------


class TestFilterSafeDefinitions:
    def test_excludes_class_def(self):
        """ClassDef is excluded — handled separately via sanitize_class_body."""
        code = "class Foo: pass"
        module = ast.parse(code)
        result = filter_safe_definitions(module.body)
        assert len(result) == 0

    def test_keeps_function_def(self):
        code = "def foo(): pass"
        module = ast.parse(code)
        result = filter_safe_definitions(module.body)
        assert len(result) == 1
        assert isinstance(result[0], ast.FunctionDef)

    def test_keeps_safe_assignment(self):
        code = 'X = 42\nY = "hello"'
        module = ast.parse(code)
        result = filter_safe_definitions(module.body)
        assert len(result) == 2

    def test_removes_assignment_with_call(self):
        code = 'result = subprocess.check_output("id", shell=True)'
        module = ast.parse(code)
        result = filter_safe_definitions(module.body)
        assert len(result) == 0

    def test_keeps_annotated_assignment_without_value(self):
        code = "x: int"
        module = ast.parse(code)
        result = filter_safe_definitions(module.body)
        assert len(result) == 1

    def test_removes_annotated_assignment_with_call(self):
        code = "x: str = os.getcwd()"
        module = ast.parse(code)
        result = filter_safe_definitions(module.body)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# sanitize_class_body
# ---------------------------------------------------------------------------


class TestSanitizeClassBody:
    def test_keeps_methods(self):
        code = dedent("""\
            class Foo:
                def run(self):
                    return "ok"
        """)
        tree = ast.parse(code)
        class_node = tree.body[0]
        sanitized = sanitize_class_body(class_node)
        assert any(isinstance(n, ast.FunctionDef) for n in sanitized.body)

    def test_keeps_safe_assignments(self):
        code = dedent("""\
            class Foo:
                display_name = "Foo"
                x = 42
        """)
        tree = ast.parse(code)
        class_node = tree.body[0]
        sanitized = sanitize_class_body(class_node)
        assert len(sanitized.body) == 2

    def test_removes_dangerous_call_in_body(self):
        code = dedent("""\
            class Foo:
                os.system("id")
                display_name = "Foo"
        """)
        tree = ast.parse(code)
        class_node = tree.body[0]
        sanitized = sanitize_class_body(class_node)
        # Only display_name assignment should remain
        assert len(sanitized.body) == 1
        assert isinstance(sanitized.body[0], ast.Assign)

    def test_removes_assignment_with_call_in_body(self):
        code = dedent("""\
            class Foo:
                result = subprocess.check_output("id", shell=True)
                display_name = "Foo"
        """)
        tree = ast.parse(code)
        class_node = tree.body[0]
        sanitized = sanitize_class_body(class_node)
        assert len(sanitized.body) == 1

    def test_keeps_docstring(self):
        code = dedent('''\
            class Foo:
                """This is a docstring."""
                pass
        ''')
        tree = ast.parse(code)
        class_node = tree.body[0]
        sanitized = sanitize_class_body(class_node)
        assert any(
            isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant) for n in sanitized.body
        )

    def test_empty_body_gets_pass(self):
        code = dedent("""\
            class Foo:
                os.system("id")
        """)
        tree = ast.parse(code)
        class_node = tree.body[0]
        sanitized = sanitize_class_body(class_node)
        assert len(sanitized.body) == 1
        assert isinstance(sanitized.body[0], ast.Pass)


# ---------------------------------------------------------------------------
# _contains_call helper
# ---------------------------------------------------------------------------


class TestContainsCall:
    def test_constant_has_no_call(self):
        node = ast.parse("42", mode="eval").body
        assert not _contains_call(node)

    def test_function_call_detected(self):
        node = ast.parse("foo()", mode="eval").body
        assert _contains_call(node)

    def test_method_call_detected(self):
        node = ast.parse("os.system('id')", mode="eval").body
        assert _contains_call(node)

    def test_nested_call_detected(self):
        node = ast.parse("[foo()]", mode="eval").body
        assert _contains_call(node)

    def test_name_has_no_call(self):
        node = ast.parse("x", mode="eval").body
        assert not _contains_call(node)


# ---------------------------------------------------------------------------
# Integration: create_class with sandbox=True
# ---------------------------------------------------------------------------


class TestCreateClassSandbox:
    def test_legitimate_component_passes(self):
        from lfx.custom.validate import create_class

        code = dedent("""\
            from langflow.custom import Component
            from langflow.io import Output

            class TestComp(Component):
                display_name = "TestComp"
                outputs = [Output(display_name="O", name="o", method="run")]
                def run(self):
                    return "hello"
        """)
        result = create_class(code, "TestComp", sandbox=True)
        assert result.__name__ == "TestComp"

    def test_subprocess_import_blocked(self):
        from lfx.custom.validate import create_class

        code = dedent("""\
            from langflow.custom import Component
            from langflow.io import Output
            import subprocess

            class Evil(Component):
                display_name = "Evil"
                outputs = [Output(display_name="O", name="o", method="run")]
                def run(self):
                    return "ok"
        """)
        with pytest.raises((ValueError, CodeSafetyError)):
            create_class(code, "Evil", sandbox=True)

    def test_socket_import_blocked(self):
        from lfx.custom.validate import create_class

        code = dedent("""\
            from langflow.custom import Component
            from langflow.io import Output
            import socket

            class Evil(Component):
                display_name = "Evil"
                outputs = [Output(display_name="O", name="o", method="run")]
                def run(self):
                    return "ok"
        """)
        with pytest.raises((ValueError, CodeSafetyError)):
            create_class(code, "Evil", sandbox=True)

    def test_dunder_import_blocked(self):
        from lfx.custom.validate import create_class

        code = dedent("""\
            from langflow.custom import Component
            from langflow.io import Output

            class Evil(Component):
                display_name = "Evil"
                outputs = [Output(display_name="O", name="o", method="run")]
                def run(self):
                    return __import__("os").system("id")
        """)
        with pytest.raises((ValueError, CodeSafetyError)):
            create_class(code, "Evil", sandbox=True)

    def test_class_body_call_removed(self):
        """Class-body code with function calls should be stripped during sandbox."""
        from lfx.custom.validate import create_class

        code = dedent("""\
            from langflow.custom import Component
            from langflow.io import Output
            import os

            class Evil(Component):
                display_name = "Evil"
                os.system("touch /tmp/sandbox_test_classbody")
                outputs = [Output(display_name="O", name="o", method="run")]
                def run(self):
                    return "ok"
        """)
        # The class should be created but the os.system call should be stripped
        result = create_class(code, "Evil", sandbox=True)
        assert result.__name__ == "Evil"

    def test_toplevel_assignment_with_call_filtered(self):
        """Top-level assignments containing function calls should be filtered."""
        from lfx.custom.validate import create_class

        code = dedent("""\
            from langflow.custom import Component
            from langflow.io import Output
            import os

            result = os.getcwd()

            class Benign(Component):
                display_name = "Benign"
                outputs = [Output(display_name="O", name="o", method="run")]
                def run(self):
                    return "ok"
        """)
        # Should succeed — the dangerous assignment is filtered out
        result = create_class(code, "Benign", sandbox=True)
        assert result.__name__ == "Benign"

    def test_runtime_mode_allows_everything(self):
        """Without sandbox, all code should execute normally."""
        from lfx.custom.validate import create_class

        code = dedent("""\
            from langflow.custom import Component
            from langflow.io import Output
            import os

            class RuntimeComp(Component):
                display_name = "RuntimeComp"
                outputs = [Output(display_name="O", name="o", method="run")]
                def run(self):
                    return os.getcwd()
        """)
        # sandbox=False (default) should not block anything
        result = create_class(code, "RuntimeComp", sandbox=False)
        assert result.__name__ == "RuntimeComp"

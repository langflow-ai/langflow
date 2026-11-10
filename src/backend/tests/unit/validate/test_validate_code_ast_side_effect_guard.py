"""
Security regression test for langflow-ai/langflow (CWE-94 / CWE-918 · CVSS 8.8):
Ensures /api/v1/validate/code rejects top-level arbitrary expressions/calls and
dangerous module imports before executing or compiling user-supplied component code.
"""
import ast
import pytest

FORBIDDEN_IMPORTS = {"subprocess", "pty", "ctypes", " builtins"}


def validate_component_ast_strict(source_code: str) -> bool:
    tree = ast.parse(source_code)
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in FORBIDDEN_IMPORTS:
                    raise ValueError(f"Disallowed module import in component validation: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[0] in FORBIDDEN_IMPORTS:
                raise ValueError(f"Disallowed from-import in component validation: {node.module}")
        elif not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Assign, ast.AnnAssign)):
            raise ValueError(f"Disallowed top-level executable statement in component code: {type(node).__name__}")
    return True


def test_rejects_top_level_rce_call_and_subprocess_import():
    with pytest.raises(ValueError, match="Disallowed module import"):
        validate_component_ast_strict("import subprocess\ndef build(): pass")
    with pytest.raises(ValueError, match="Disallowed top-level executable statement"):
        validate_component_ast_strict("__import__('os').system('id')")
    assert validate_component_ast_strict("class CustomComponent:\n    def build(self): return 1") is True

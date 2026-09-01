"""Static guard for the async-aware Langflow logger API."""

from __future__ import annotations

import ast
from pathlib import Path

_ASYNC_LOG_METHODS = frozenset({"adebug", "ainfo", "awarning", "aerror", "aexception", "acritical"})
_REPO_ROOT = Path(__file__).resolve().parents[4]
_SOURCE_ROOTS = (_REPO_ROOT / "src" / "backend", _REPO_ROOT / "src" / "lfx")


def _logger_method(call: ast.Call) -> str | None:
    func = call.func
    if not isinstance(func, ast.Attribute) or not isinstance(func.value, ast.Name) or func.value.id != "logger":
        return None
    return func.attr


def _python_sources() -> list[Path]:
    return sorted(path for root in _SOURCE_ROOTS for path in root.rglob("*.py") if ".venv" not in path.parts)


def test_async_logger_calls_are_not_discarded_expression_statements() -> None:
    violations: list[str] = []
    for path in _python_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call):
                continue
            method = _logger_method(node.value)
            relative = path.relative_to(_REPO_ROOT)
            if method in _ASYNC_LOG_METHODS:
                violations.append(f"{relative}:{node.lineno}: discarded logger.{method}() coroutine")

    assert not violations, "\n" + "\n".join(violations)

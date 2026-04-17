"""AST helpers for Phase 4 structural assertions.

Source: docs.python.org/3/library/ast.html

These helpers support Phase 4 D-06 (SVC-02 gather structure), D-07
(SVC-03 ``asyncio.sleep(10.0)`` absence), and D-10 (gather-review-table
enforcement) tests. They parse ``src/backend/base/langflow/main.py`` once and
expose a tiny query API over the AST.
"""

from __future__ import annotations

import ast
from pathlib import Path

_LIFESPAN_MODULE_PATH = Path("src/backend/base/langflow/main.py")


def parse_lifespan_module() -> ast.Module:
    """Parse ``src/backend/base/langflow/main.py`` and return its AST.

    Uses a repo-relative path (the tests run from the repo root under
    ``uv run pytest``), matching the convention used by the other source-level
    assertion tests (e.g. ``test_main_superuser_init.py``).
    """
    src = _LIFESPAN_MODULE_PATH.read_text(encoding="utf-8")
    return ast.parse(src, filename="langflow/main.py")


def find_calls_to(tree: ast.AST, qualname: str) -> list[ast.Call]:
    """Find all ``Call`` nodes whose callee matches ``qualname``.

    Supports:
    - Single-segment names ("foo") matched against ``Call(func=Name('foo'))``.
    - Two-segment qualified names ("asyncio.gather") matched against
      ``Call(func=Attribute(value=Name('asyncio'), attr='gather'))``.

    Longer dotted paths are not currently needed by Phase 4 and are not
    supported.
    """
    parts = qualname.split(".")
    matches: list[ast.Call] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if len(parts) == 2:
            if (
                isinstance(func, ast.Attribute)
                and func.attr == parts[1]
                and isinstance(func.value, ast.Name)
                and func.value.id == parts[0]
            ):
                matches.append(node)
        elif len(parts) == 1 and isinstance(func, ast.Name) and func.id == parts[0]:
            matches.append(node)
    return matches


def find_sleep_with_value(tree: ast.AST, value: float) -> list[ast.Call]:
    """Return ``asyncio.sleep(<value>)`` calls where the first arg is a literal number.

    Non-literal arguments (e.g. ``asyncio.sleep(timeout_var)``) are ignored --
    they are not regressions of the Phase 3 / 4 "no magic sleep(10.0)"
    constraint. The literal check exactly matches what D-07 absence assertions
    care about.
    """
    return [
        call
        for call in find_calls_to(tree, "asyncio.sleep")
        if call.args
        and isinstance(call.args[0], ast.Constant)
        and isinstance(call.args[0].value, (int, float))
        and float(call.args[0].value) == value
    ]


def extract_gather_task_names(call: ast.Call) -> list[str]:
    """Return the callable names passed to an ``asyncio.gather(...)`` ``Call`` node.

    For ``asyncio.gather(foo(), bar.baz())`` returns ``["foo", "baz"]``.

    Gotcha (Pattern 2 / 04-PATTERNS.md): when Phase 4's SVC-02 work lands, each
    gather argument is wrapped via ``_safe_step("name", foo())``. The real task
    callable is ``arg.args[1]``, not ``_safe_step`` itself. This helper unwraps
    one level so the D-10 review-table enforcement test sees the actual task
    names.
    """
    names: list[str] = []
    for arg in call.args:
        if not isinstance(arg, ast.Call):
            continue
        callee = _extract_callee_name(arg)
        # Unwrap _safe_step("name", real_call()) one level deeper.
        if callee == "_safe_step" and len(arg.args) >= 2 and isinstance(arg.args[1], ast.Call):
            inner = _extract_callee_name(arg.args[1])
            if inner is not None:
                names.append(inner)
            continue
        if callee is not None:
            names.append(callee)
    return names


def _extract_callee_name(call: ast.Call) -> str | None:
    """Return the rightmost identifier of a ``Call.func``, or ``None`` if unrecognized."""
    func = call.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None

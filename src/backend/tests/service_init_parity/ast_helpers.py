"""AST helpers for structural assertions.

Source: docs.python.org/3/library/ast.html

These helpers support (SVC-02 gather structure),
(SVC-03 ``asyncio.sleep(10.0)`` absence), and (gather-review-table
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

    Longer dotted paths are not currently needed by and are not
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
    constraint. The literal check exactly matches what absence assertions
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

    Two levels of unwrapping are applied so the review-table enforcement
    test sees the *actual* task names regardless of the transport wrapper used:

    1. ``_safe_step("name", real_call())`` -> look at ``arg.args[1]``. Phase 4
       Pattern 2 wraps every gather argument this way for per-task exception
       isolation (see 04-PATTERNS.md).
    2. ``asyncio.to_thread(fn, ...)`` -> return ``fn``'s name. Sync callables
       like ``setup_llm_caching`` are wrapped in ``asyncio.to_thread`` so they
       don't block the event loop while sibling coroutines run. The transport
       is bookkeeping; the *task identity* is the function being scheduled.
    """
    names: list[str] = []
    for arg in call.args:
        if not isinstance(arg, ast.Call):
            continue
        callee = _extract_callee_name(arg)
        # Unwrap _safe_step("name", real_call()) one level deeper.
        if callee == "_safe_step" and len(arg.args) >= 2 and isinstance(arg.args[1], ast.Call):
            inner_call = arg.args[1]
            inner_name = _extract_callee_name(inner_call)
            # Further unwrap asyncio.to_thread(fn, ...) -> fn's name.
            if inner_name == "to_thread" and inner_call.args:
                first = inner_call.args[0]
                if isinstance(first, ast.Name):
                    names.append(first.id)
                    continue
                if isinstance(first, ast.Attribute):
                    names.append(first.attr)
                    continue
            if inner_name is not None:
                names.append(inner_name)
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

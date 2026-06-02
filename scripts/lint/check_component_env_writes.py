#!/usr/bin/env python3
"""CI guard: components must not WRITE to ``os.environ``.

``os.environ`` is process-global. A warm, long-lived serving process (``lfx serve``'s
worker pool, or the main Langflow server) handles many callers' requests in one
process, so a per-request write like ``os.environ["OPENAI_API_KEY"] = caller_key``
bleeds into other requests on that worker and persists until overwritten — leaking
one caller's credential to another. (The bleed is per-worker: uvicorn ``--workers N``
are separate processes, but every concurrent request inside one worker shares its
``os.environ``.)

READS are fine — this guard only flags WRITES. Pass per-request values through the
component's config/params instead of mutating the environment.

This walks every component source file (stdlib AST only — zero dependency on the lfx
package, since CI may run before it is importable) and flags:

    os.environ[k] = v            os.environ = {...}        del os.environ[k]
    os.environ.update(...)       os.environ.setdefault(...)    .pop/.clear/.popitem
    os.putenv(...)               os.unsetenv(...)          load_dotenv(...)

Usage::

    python scripts/lint/check_component_env_writes.py            # scan default roots
    python scripts/lint/check_component_env_writes.py FILE...     # check specific files
    python scripts/lint/check_component_env_writes.py --root path/to/components

Exit codes:
    0 -- no disallowed env writes
    1 -- one or more disallowed env writes (or a file failed to parse)
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Component source roots (matches scripts/migrate/check_bare_names.py coverage).
DEFAULT_ROOTS = (
    "src/lfx/src/lfx/components",
    "src/backend/base/langflow/components",
    "src/bundles",
)

# Deliberate, reviewed exceptions: repo-relative path -> set of allowed violation kinds.
# Keep this list tiny and justified; an entry here means "this component is knowingly
# allowed to mutate the process environment". Prefer fixing the component over adding one.
ALLOWLIST: dict[str, set[str]] = {
    # The "Dotenv" component's entire purpose is to load a user-supplied .env blob into
    # the process environment. It is a known multi-tenant hazard flagged for separate
    # review; allow only the load_dotenv call, still flagging any direct os.environ write.
    "src/lfx/src/lfx/components/datastax/dotenv.py": {"load_dotenv"},
}

_MUTATING_METHODS = {"setdefault", "update", "pop", "clear", "popitem", "__setitem__", "__delitem__"}


class _EnvWriteVisitor(ast.NodeVisitor):
    """Flags writes to ``os.environ`` (and ``load_dotenv()``), import-alias-aware.

    A first pass over the tree collects local names that refer to ``os``,
    ``os.environ``, ``os.putenv``, ``os.unsetenv`` and ``dotenv.load_dotenv``
    (including ``as``-aliases), so ``import os as system; system.environ[X]=Y``
    and ``from dotenv import load_dotenv as ld; ld()`` are caught.
    """

    def __init__(self) -> None:
        self.violations: list[tuple[int, str, str]] = []  # (lineno, kind, snippet)
        self.os_aliases: set[str] = {"os"}
        self.environ_aliases: set[str] = {"environ"}
        self.putenv_aliases: set[str] = set()
        self.unsetenv_aliases: set[str] = set()
        self.load_dotenv_aliases: set[str] = {"load_dotenv"}

    # First pass: collect import aliases module-wide (over-broad on scope is fine for a
    # security lint — we'd rather flag a write that imports `os` locally than miss it).
    def collect_aliases(self, tree: ast.AST) -> None:
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "os":
                        self.os_aliases.add(alias.asname or alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module == "os":
                    for alias in node.names:
                        local = alias.asname or alias.name
                        if alias.name == "environ":
                            self.environ_aliases.add(local)
                        elif alias.name == "putenv":
                            self.putenv_aliases.add(local)
                        elif alias.name == "unsetenv":
                            self.unsetenv_aliases.add(local)
                elif node.module == "dotenv":
                    for alias in node.names:
                        if alias.name == "load_dotenv":
                            self.load_dotenv_aliases.add(alias.asname or alias.name)

    def _is_environ(self, node: ast.AST) -> bool:
        """True for ``<os_alias>.environ`` or a bare ``<environ_alias>``."""
        if isinstance(node, ast.Attribute):
            return node.attr == "environ" and isinstance(node.value, ast.Name) and node.value.id in self.os_aliases
        return isinstance(node, ast.Name) and node.id in self.environ_aliases

    def _flag(self, lineno: int, kind: str, snippet: str) -> None:
        self.violations.append((lineno, kind, snippet))

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            if isinstance(target, ast.Subscript) and self._is_environ(target.value):
                self._flag(node.lineno, "assign", "os.environ[...] = ...")
            elif self._is_environ(target):
                self._flag(node.lineno, "rebind", "os.environ = ...")
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if isinstance(node.target, ast.Subscript) and self._is_environ(node.target.value):
            self._flag(node.lineno, "assign", "os.environ[...]: ... = ...")
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        target = node.target
        if (isinstance(target, ast.Subscript) and self._is_environ(target.value)) or self._is_environ(target):
            self._flag(node.lineno, "assign", "os.environ augmented assignment")
        self.generic_visit(node)

    def visit_Delete(self, node: ast.Delete) -> None:
        for target in node.targets:
            if isinstance(target, ast.Subscript) and self._is_environ(target.value):
                self._flag(node.lineno, "del", "del os.environ[...]")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        if isinstance(func, ast.Attribute):
            if func.attr in _MUTATING_METHODS and self._is_environ(func.value):
                self._flag(node.lineno, f"mutate:{func.attr}", f"os.environ.{func.attr}(...)")
            elif (
                func.attr in {"putenv", "unsetenv"}
                and isinstance(func.value, ast.Name)
                and func.value.id in self.os_aliases
            ):
                self._flag(node.lineno, func.attr, f"os.{func.attr}(...)")
            elif func.attr == "load_dotenv":
                self._flag(node.lineno, "load_dotenv", "load_dotenv(...)")
        elif isinstance(func, ast.Name):
            if func.id in self.putenv_aliases:
                self._flag(node.lineno, "putenv", f"{func.id}(...)")
            elif func.id in self.unsetenv_aliases:
                self._flag(node.lineno, "unsetenv", f"{func.id}(...)")
            elif func.id in self.load_dotenv_aliases:
                self._flag(node.lineno, "load_dotenv", f"{func.id}(...)")
        self.generic_visit(node)


def _iter_py_files(roots: list[Path]) -> list[Path]:
    files: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.py")):
            parts = path.parts
            if "tests" in parts or path.name.startswith("test_"):
                continue
            files.append(path)
    return files


def _check_file(path: Path) -> list[tuple[str, int, str, str]]:
    try:
        rel = path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        rel = path.as_posix()
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError) as exc:
        return [(rel, getattr(exc, "lineno", 0) or 0, "parse-error", str(exc))]
    visitor = _EnvWriteVisitor()
    visitor.collect_aliases(tree)
    visitor.visit(tree)
    allowed = ALLOWLIST.get(rel, set())
    out: list[tuple[str, int, str, str]] = []
    for lineno, kind, snippet in visitor.violations:
        if kind in allowed:
            continue
        out.append((rel, lineno, kind, snippet))
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("files", nargs="*", help="Specific files to check (default: scan component roots).")
    parser.add_argument("--root", action="append", default=None, help="Override component root(s) to scan.")
    args = parser.parse_args(argv)

    if args.files:
        targets = [Path(f).resolve() for f in args.files if f.endswith(".py")]
    else:
        roots = [Path(r) if Path(r).is_absolute() else REPO_ROOT / r for r in (args.root or DEFAULT_ROOTS)]
        targets = _iter_py_files(roots)

    violations: list[tuple[str, int, str, str]] = []
    for path in targets:
        violations.extend(_check_file(path))

    if not violations:
        return 0

    print("ERROR: component(s) write to os.environ (process-global — bleeds across requests")
    print("       in a shared serving process such as `lfx serve`):\n")
    for rel, lineno, kind, snippet in sorted(violations):
        print(f"  {rel}:{lineno}  [{kind}]  {snippet}")
    print(
        "\nFix: pass per-request values through the component's config/params, not the\n"
        "process environment (reads are fine; only writes bleed). If a write is a\n"
        "deliberate, reviewed exception, add it to ALLOWLIST in\n"
        "scripts/lint/check_component_env_writes.py with a justification."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())

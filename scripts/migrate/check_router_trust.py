#!/usr/bin/env python3
"""CI guard: forbid install/uninstall/registry-mutation routes under /api/v1/extensions/**.

Per the Extension System trust boundary (Bundle Separation: Developer
Guide, section 4): "Install / uninstall / registry mutation never happens
at runtime on a live production server.  The router-trust CI guard in
LE-1017 enforces this: any handler under ``/api/v1/extensions/**``
matching install, uninstall, registry_add, or registry_remove fails CI."

The guard scans every ``.py`` file under the configured roots, parses
each one with the AST module, and resolves cross-file ``include_router``
chains so a forbidden handler in module A cannot slip through by being
mounted under ``/extensions`` in module B.

Resolution model
----------------

A router instance is identified by ``(source_file, var_name)``.  A
router is "in scope" -- meaning its decorators must be checked -- if any
of these hold:

    1. It was constructed with ``APIRouter(prefix="...extensions...")``
       in its source file.
    2. Its source file contains the line ``# router-trust: in-scope``
       (escape hatch for non-literal prefixes computed at runtime).
    3. Some file calls ``parent.include_router(this, prefix="...extensions...")``
       where ``this`` resolves to the router's source file.
    4. Some file calls ``parent.include_router(this, prefix=...)`` where
       ``parent`` is itself in scope (transitive).

Resolution follows ``from <module> import <name> [as <alias>]`` imports
across the project's two Python package roots
(``src/backend/base`` and ``src/lfx/src``).  Relative imports are
handled.  An imported router that cannot be statically resolved is
ignored -- the guard never flags routes it cannot prove are reachable
from ``/extensions``, but a route declared in the same file as an
in-scope router IS flagged.

Forbidden tokens (kebab- and snake-case both):
    install, uninstall, registry-add, registry_add,
    registry-remove, registry_remove

Allowlisted substrings:
    installed-extension-immutable, installed_extension_immutable,
    _uninstall_immutable

These are typed-error code strings, not routes; they appear in
function bodies / typed-error payloads and must not trip the guard.

Exit codes:
    0 -- no forbidden routes
    1 -- forbidden route found (details to stderr)
    2 -- usage / IO / parse error
"""

from __future__ import annotations

import argparse
import ast
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]

# Walk every ``.py`` file under each root.
SCAN_ROOTS: tuple[Path, ...] = (
    REPO_ROOT / "src" / "backend" / "base" / "langflow" / "api",
    REPO_ROOT / "src" / "lfx" / "src" / "lfx",
)

# Python package roots.  Used to resolve ``from <module> import <name>``
# back to a file path -- ``langflow.api.v1.extensions`` lives under
# ``src/backend/base/`` and ``lfx.extension.bundle_registry`` lives under
# ``src/lfx/src/``.
MODULE_ROOTS: tuple[Path, ...] = (
    REPO_ROOT / "src" / "backend" / "base",
    REPO_ROOT / "src" / "lfx" / "src",
)

FORBIDDEN_TOKENS: tuple[str, ...] = (
    "install",
    "uninstall",
    "registry_add",
    "registry-add",
    "registry_remove",
    "registry-remove",
)

ALLOWED_SUBSTRINGS: tuple[str, ...] = (
    "installed-extension-immutable",
    "installed_extension_immutable",
    "_uninstall_immutable",
)

HTTP_METHODS = frozenset({"get", "post", "put", "patch", "delete", "options", "head"})

IN_SCOPE_MARKER = "# router-trust: in-scope"

# An import like ``from foo import bar`` produces a dotted target with at
# least one dot ("foo.bar").  Names with fewer dots cannot be resolved to a
# (module, name) pair.
_MIN_DOTTED_PARTS = 2


# ---------------------------------------------------------------------------
# Per-file collected info
# ---------------------------------------------------------------------------


@dataclass
class IncludeCall:
    parent_var: str
    child_var: str
    child_prefix: str | None
    lineno: int


@dataclass
class DecoratorRef:
    router_var: str
    method: str
    path: str
    lineno: int
    func_name: str


@dataclass
class FileInfo:
    path: Path
    # var -> prefix string (None if no prefix kwarg)
    local_routers: dict[str, str | None] = field(default_factory=dict)
    # alias -> "<module>.<name>" (resolved import target)
    imports: dict[str, str] = field(default_factory=dict)
    include_calls: list[IncludeCall] = field(default_factory=list)
    decorators: list[DecoratorRef] = field(default_factory=list)
    has_marker: bool = False


RouterId = tuple[Path, str]


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def _is_apirouter_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Name) and func.id == "APIRouter":
        return True
    return bool(isinstance(func, ast.Attribute) and func.attr == "APIRouter")


def _kwarg_string(call: ast.Call, name: str) -> str | None:
    for kw in call.keywords:
        if kw.arg == name and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
            return kw.value.value
    return None


def _module_for_file(path: Path) -> str | None:
    """Convert ``foo/bar.py`` under one of the module roots into ``foo.bar``."""
    for root in MODULE_ROOTS:
        try:
            rel = path.resolve().relative_to(root.resolve())
        except ValueError:
            continue
        parts = list(rel.parts)
        if not parts:
            return None
        if parts[-1] == "__init__.py":
            parts = parts[:-1]
        elif parts[-1].endswith(".py"):
            parts[-1] = parts[-1][:-3]
        if not parts:
            return None
        return ".".join(parts)
    return None


def _resolve_relative_module(file_module: str, level: int, module: str | None) -> str | None:
    """Apply Python's relative-import rules to compute the absolute module name."""
    if level == 0:
        return module
    parts = file_module.split(".")
    # Walk up ``level`` packages.  The current module's last segment is the
    # *file* name (or the empty string for ``__init__.py`` which has no
    # trailing segment).  Python's semantics: level=1 means "current
    # package"; level=2 means "parent package"; etc.
    if len(parts) < level:
        return None
    base = parts[: len(parts) - level]
    if module:
        base.extend(module.split("."))
    return ".".join(base) if base else None


def _module_to_file(module: str) -> Path | None:
    parts = module.split(".")
    if not parts:
        return None
    for root in MODULE_ROOTS:
        candidate = root.joinpath(*parts).with_suffix(".py")
        if candidate.exists():
            return candidate
        candidate = root.joinpath(*parts) / "__init__.py"
        if candidate.exists():
            return candidate
    return None


def parse_file(path: Path) -> FileInfo | None:
    """Parse one file with AST; return None on syntax error."""
    try:
        source = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return None

    info = FileInfo(path=path, has_marker=IN_SCOPE_MARKER in source)
    file_module = _module_for_file(path) or ""

    for node in ast.walk(tree):
        # APIRouter(...) assignments
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            target_name = node.targets[0].id
            if _is_apirouter_call(node.value):
                prefix = _kwarg_string(node.value, "prefix")
                info.local_routers[target_name] = prefix

        # Imports
        if isinstance(node, ast.ImportFrom):
            module = _resolve_relative_module(file_module, node.level, node.module)
            if module:
                for alias in node.names:
                    local_name = alias.asname or alias.name
                    info.imports[local_name] = f"{module}.{alias.name}"
        elif isinstance(node, ast.Import):
            for alias in node.names:
                local_name = alias.asname or alias.name.split(".")[0]
                info.imports[local_name] = alias.name

        # parent.include_router(child, prefix=...)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "include_router"
            and isinstance(node.func.value, ast.Name)
            and node.args
            and isinstance(node.args[0], ast.Name)
        ):
            parent_var = node.func.value.id
            child_var = node.args[0].id
            prefix = _kwarg_string(node, "prefix")
            info.include_calls.append(
                IncludeCall(
                    parent_var=parent_var,
                    child_var=child_var,
                    child_prefix=prefix,
                    lineno=node.lineno,
                )
            )

        # @<router>.<method>(...) on a (Async)FunctionDef
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for deco in node.decorator_list:
                if (
                    isinstance(deco, ast.Call)
                    and isinstance(deco.func, ast.Attribute)
                    and deco.func.attr in HTTP_METHODS
                    and isinstance(deco.func.value, ast.Name)
                ):
                    router_var = deco.func.value.id
                    path_str = ""
                    if deco.args and isinstance(deco.args[0], ast.Constant) and isinstance(deco.args[0].value, str):
                        path_str = deco.args[0].value
                    info.decorators.append(
                        DecoratorRef(
                            router_var=router_var,
                            method=deco.func.attr,
                            path=path_str,
                            lineno=deco.lineno,
                            func_name=node.name,
                        )
                    )

    return info


# ---------------------------------------------------------------------------
# Resolution + scope computation
# ---------------------------------------------------------------------------


def _resolve_var(file_info: FileInfo, var: str, file_info_map: dict[Path, FileInfo]) -> RouterId | None:
    """Map ``var`` (a name in ``file_info``) to the (file, var) where it's defined."""
    if var in file_info.local_routers:
        return (file_info.path, var)
    if var in file_info.imports:
        full = file_info.imports[var]
        parts = full.split(".")
        if len(parts) < _MIN_DOTTED_PARTS:
            return None
        module = ".".join(parts[:-1])
        target_name = parts[-1]
        target_file = _module_to_file(module)
        if target_file is None:
            return None
        target_info = file_info_map.get(target_file)
        if target_info is None:
            return None
        if target_name in target_info.local_routers:
            return (target_file, target_name)
        # Re-export chain: the target file may itself import this name.
        if target_name in target_info.imports:
            return _resolve_var(target_info, target_name, file_info_map)
    return None


def compute_in_scope(file_info_map: dict[Path, FileInfo]) -> set[RouterId]:
    in_scope: set[RouterId] = set()

    # Seed: APIRouter(prefix=".../extensions...")
    for path, info in file_info_map.items():
        for var, prefix in info.local_routers.items():
            if prefix and "/extensions" in prefix:
                in_scope.add((path, var))

    # Seed: explicit marker -> every local router in the file
    for path, info in file_info_map.items():
        if info.has_marker:
            for var in info.local_routers:
                in_scope.add((path, var))

    # Iterate: propagate via include_router calls
    changed = True
    while changed:
        changed = False
        for info in file_info_map.values():
            for call in info.include_calls:
                child_id = _resolve_var(info, call.child_var, file_info_map)
                if child_id is None or child_id in in_scope:
                    continue
                child_in_scope = False
                if call.child_prefix and "/extensions" in call.child_prefix:
                    child_in_scope = True
                else:
                    parent_id = _resolve_var(info, call.parent_var, file_info_map)
                    if parent_id is not None and parent_id in in_scope:
                        child_in_scope = True
                if child_in_scope:
                    in_scope.add(child_id)
                    changed = True

    return in_scope


# ---------------------------------------------------------------------------
# Forbidden-token check
# ---------------------------------------------------------------------------


def _violation_token(text: str) -> str | None:
    lowered = text.lower()
    for allowed in ALLOWED_SUBSTRINGS:
        lowered = lowered.replace(allowed, "")
    for token in FORBIDDEN_TOKENS:
        if token in lowered:
            return token
    return None


def scan_in_scope(
    file_info_map: dict[Path, FileInfo],
    in_scope: set[RouterId],
) -> list[str]:
    violations: list[str] = []
    in_scope_files: dict[Path, set[str]] = {}
    for path, var in in_scope:
        in_scope_files.setdefault(path, set()).add(var)

    for path, info in file_info_map.items():
        target_vars = in_scope_files.get(path)
        # If the file has the explicit marker, every decorator counts -- we
        # cannot trust ``router_var`` to be a literal name.
        check_all = info.has_marker
        if not target_vars and not check_all:
            continue

        for deco in info.decorators:
            if not check_all and deco.router_var not in (target_vars or set()):
                continue
            token = _violation_token(deco.path) or _violation_token(deco.func_name)
            if token is not None:
                violations.append(
                    f"{path}:{deco.lineno}: forbidden token {token!r} in handler "
                    f"@{deco.router_var}.{deco.method}({deco.path!r}) def {deco.func_name}(...)"
                )
    return violations


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def discover_paths(roots: tuple[Path, ...]) -> list[Path]:
    out: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            out.append(path)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--paths",
        nargs="*",
        type=Path,
        default=None,
        help=(
            "Override the default scan with an explicit file list "
            "(mostly useful for tests).  When unset, every ``.py`` under "
            "the configured scan roots is walked."
        ),
    )
    args = parser.parse_args()

    targets = list(args.paths) if args.paths else discover_paths(SCAN_ROOTS)

    file_info_map: dict[Path, FileInfo] = {}
    for path in targets:
        info = parse_file(path)
        if info is not None:
            file_info_map[path] = info

    in_scope = compute_in_scope(file_info_map)
    violations = scan_in_scope(file_info_map, in_scope)

    if violations:
        print(
            "router-trust guard: forbidden install/uninstall/registry-mutation route detected.",
            file=sys.stderr,
        )
        print(
            "These verbs MUST NOT live under /api/v1/extensions/** -- per the trust",
            file=sys.stderr,
        )
        print(
            "boundary, install / uninstall / registry mutation happens via pip in",
            file=sys.stderr,
        )
        print(
            "Mode A or via the Dockerfile in Mode B/C, never at runtime on a live",
            file=sys.stderr,
        )
        print("server.\n", file=sys.stderr)
        for violation in violations:
            print(f"  - {violation}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

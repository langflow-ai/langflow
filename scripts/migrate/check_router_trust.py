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


# ---------------------------------------------------------------------------
# Per-file collected info
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ImportTarget:
    """What an alias in a file's namespace refers to.

    Two kinds:
        * ``kind="from"`` -- ``from <module> import <name> [as alias]``;
          the alias names a *value* (router, function, etc.) inside
          ``<module>``.
        * ``kind="module"`` -- ``import <module> [as alias]``; the alias
          names a *module*.  Accessing ``.x`` either descends into a
          submodule or pulls a value out of the module.

    Kept as its own dataclass so the resolver can branch on the import
    shape without re-deriving it from the raw string.
    """

    kind: str  # "from" or "module"
    module: str  # the module path (for "from": the source module; for "module": the imported module path)
    name: str | None = None  # for "from": the imported name; for "module": None


@dataclass
class IncludeCall:
    parent_chain: tuple[str, ...]
    child_chain: tuple[str, ...]
    child_prefix: str | None
    lineno: int


@dataclass
class DecoratorRef:
    router_chain: tuple[str, ...]
    method: str
    path: str
    lineno: int
    func_name: str


@dataclass
class FileInfo:
    path: Path
    # var -> prefix string (None if no prefix kwarg)
    local_routers: dict[str, str | None] = field(default_factory=dict)
    # alias -> ImportTarget describing what the alias refers to
    imports: dict[str, ImportTarget] = field(default_factory=dict)
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


# Sentinel returned when ``_kwarg_string`` finds a kwarg that's present but
# not a static string literal -- e.g. ``prefix=f"/extensions/{tenant}"`` or
# ``prefix=PREFIX_VAR``.  Treated as "in scope by default" by
# :func:`compute_in_scope` so a dynamic prefix cannot smuggle handlers past
# the guard; the alternative (silently treating an unresolvable prefix as
# absent) means an f-string-prefixed router falls through the analysis.
_UNRESOLVABLE_PREFIX = "<router-trust:unresolvable-prefix>"


def _kwarg_string(call: ast.Call, name: str) -> str | None:
    for kw in call.keywords:
        if kw.arg != name:
            continue
        if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
            return kw.value.value
        # Kwarg is present but not a literal string -- f-string, variable,
        # or anything else we cannot resolve statically.  Surface the
        # sentinel so the in-scope seeder treats it conservatively.
        return _UNRESOLVABLE_PREFIX
    return None


def _module_for_file(path: Path) -> tuple[str, bool] | None:
    """Return ``(dotted_module, is_package)`` for *path*.

    ``is_package`` is ``True`` for ``__init__.py`` files (which represent
    the package itself, not a module *inside* the package).  This matters
    for relative-import resolution: ``from .x import y`` inside
    ``pkg/__init__.py`` resolves to ``pkg.x``, but the same statement
    inside ``pkg/main.py`` also resolves to ``pkg.x`` -- the anchor
    differs because ``main.py``'s file_module is ``pkg.main`` while
    ``__init__.py``'s file_module is ``pkg``.
    """
    for root in MODULE_ROOTS:
        try:
            rel = path.resolve().relative_to(root.resolve())
        except ValueError:
            continue
        parts = list(rel.parts)
        if not parts:
            return None
        is_package = parts[-1] == "__init__.py"
        if is_package:
            parts = parts[:-1]
        elif parts[-1].endswith(".py"):
            parts[-1] = parts[-1][:-3]
        if not parts:
            return None
        return ".".join(parts), is_package
    return None


def _resolve_relative_module(
    file_module: str,
    *,
    is_package: bool,
    level: int,
    module: str | None,
) -> str | None:
    """Apply Python's relative-import rules to compute the absolute module name.

    Per PEP 328:
        * Inside a regular module ``pkg.foo`` (``pkg/foo.py``), ``level=1``
          anchors at the *parent package* ``pkg``: ``from .x import y``
          resolves to ``pkg.x``.
        * Inside a package ``pkg`` (``pkg/__init__.py``), ``level=1``
          anchors at *the package itself* ``pkg``: ``from .x import y``
          inside ``pkg/__init__.py`` also resolves to ``pkg.x``, but the
          arithmetic is different because the file's own dotted module is
          ``pkg``, not ``pkg.__init__``.

    The ``is_package`` flag tells us which arithmetic to apply -- it
    decrements ``level`` by one for ``__init__.py`` files so the anchor
    lands on the right package in both cases.
    """
    if level == 0:
        return module
    parts = file_module.split(".")
    # For packages, the file IS the anchor; level=1 means "stay here".
    # For modules, level=1 means "go up one to the enclosing package".
    steps = level - 1 if is_package else level
    if len(parts) < steps:
        return None
    base = parts[: len(parts) - steps]
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


def _attribute_chain(node: ast.AST) -> tuple[str, ...] | None:
    """Flatten an ``ast.Name`` / ``ast.Attribute`` chain into a tuple of segments.

    ``foo`` -> ``("foo",)``
    ``foo.bar`` -> ``("foo", "bar")``
    ``foo.bar.baz`` -> ``("foo", "bar", "baz")``
    Anything else (subscript, call, etc.) -> ``None``.
    """
    parts: list[str] = []
    current: ast.AST = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if not isinstance(current, ast.Name):
        return None
    parts.append(current.id)
    parts.reverse()
    return tuple(parts)


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
    module_info = _module_for_file(path)
    if module_info is None:
        file_module = ""
        is_package = False
    else:
        file_module, is_package = module_info

    for node in ast.walk(tree):
        # APIRouter(...) assignments
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            target_name = node.targets[0].id
            if _is_apirouter_call(node.value):
                prefix = _kwarg_string(node.value, "prefix")
                info.local_routers[target_name] = prefix

        # Imports.  We record the *kind* of import so the resolver can
        # distinguish ``from X import Y`` (Y is a value) from ``import X.Y``
        # (where X.Y is itself a module and ``X.Y.router`` is the value).
        if isinstance(node, ast.ImportFrom):
            module = _resolve_relative_module(file_module, is_package=is_package, level=node.level, module=node.module)
            if module:
                for alias in node.names:
                    local_name = alias.asname or alias.name
                    info.imports[local_name] = ImportTarget(kind="from", module=module, name=alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                local_name = alias.asname or alias.name.split(".")[0]
                info.imports[local_name] = ImportTarget(kind="module", module=alias.name, name=None)

        # parent.include_router(child, prefix=...).  Both parent and child
        # may be ``ast.Attribute`` chains (``app.api.include_router(...)``
        # or ``include_router(child.api.router, ...)``), so we flatten both
        # sides into tuples and let the resolver handle the dotted form.
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "include_router"
            and node.args
        ):
            parent_chain = _attribute_chain(node.func.value)
            child_chain = _attribute_chain(node.args[0])
            if parent_chain is not None and child_chain is not None:
                prefix = _kwarg_string(node, "prefix")
                info.include_calls.append(
                    IncludeCall(
                        parent_chain=parent_chain,
                        child_chain=child_chain,
                        child_prefix=prefix,
                        lineno=node.lineno,
                    )
                )

        # @<router>.<method>(...) on a (Async)FunctionDef.  The router
        # reference can also be a dotted attribute chain
        # (``@child.api.router.post(...)``), so flatten it too.
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for deco in node.decorator_list:
                if (
                    isinstance(deco, ast.Call)
                    and isinstance(deco.func, ast.Attribute)
                    and deco.func.attr in HTTP_METHODS
                ):
                    router_chain = _attribute_chain(deco.func.value)
                    if router_chain is None:
                        continue
                    path_str = ""
                    if deco.args and isinstance(deco.args[0], ast.Constant) and isinstance(deco.args[0].value, str):
                        path_str = deco.args[0].value
                    info.decorators.append(
                        DecoratorRef(
                            router_chain=router_chain,
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


def _resolve_chain(
    file_info: FileInfo,
    chain: tuple[str, ...],
    file_info_map: dict[Path, FileInfo],
    *,
    seen: frozenset[tuple[Path, tuple[str, ...]]] = frozenset(),
) -> RouterId | None:
    """Map a dotted attribute chain to the (file, var_name) defining the router.

    Handles four name shapes (the ``A``/``B``/``C``/``D`` correspond to
    cases enumerated in this script's docstring):

      A. ``from X.Y import Z`` then ``Z`` -> chain=("Z",)
      B. ``from X.Y import Z as alias`` then ``alias`` -> chain=("alias",)
      C. ``import X.Y`` then ``X.Y.Z`` -> chain=("X","Y","Z")
      D. ``import X.Y as alias`` then ``alias.Z`` -> chain=("alias","Z")

    Cycles in re-export chains (``a.py`` re-exports from ``b.py`` which
    re-exports from ``a.py``) are bounded via the ``seen`` set; the
    resolver returns ``None`` rather than recursing forever.
    """
    if not chain:
        return None
    head = chain[0]
    rest = chain[1:]

    # Bound recursion against re-export cycles.
    fingerprint = (file_info.path, chain)
    if fingerprint in seen:
        return None
    seen = seen | {fingerprint}

    # Local definition (only meaningful for a single Name, not an
    # attribute chain -- ``foo.bar`` cannot resolve to a local variable
    # ``foo`` because that would be a method call, not a router lookup).
    if not rest and head in file_info.local_routers:
        return (file_info.path, head)

    if head not in file_info.imports:
        return None
    imp = file_info.imports[head]

    if imp.kind == "from":
        if not rest:
            # `from M import N [as alias]; alias` -> module=M, var=N
            module = imp.module
            var = imp.name
        else:
            # `from M import N [as alias]; alias.x.y...`
            # Treat alias as a value living at M.N; the chain after head
            # walks deeper (rare for routers but handle it cleanly).
            module = ".".join([imp.module, *([imp.name] if imp.name else []), *rest[:-1]])
            var = rest[-1]
        if not var:
            return None
    elif imp.kind == "module":
        # ``import M [as alias]``; ``imp.module`` is M.
        if head == imp.module:
            # Case where head is the literal module path (``import x``;
            # alias matches "x" exactly).  ``head.x.y`` -> module=M+x, var=y.
            if not rest:
                return None
            module = ".".join([imp.module, *rest[:-1]])
            var = rest[-1]
        elif imp.module.startswith(head + "."):
            # Case C: ``import x.y.z`` (no asname).  Python's binding rule:
            # the local name is the *first* segment ("x"); the rest of the
            # dotted path lives under it.  Code references must spell out
            # the full module path before the var: ``x.y.z.router``.
            module_parts = tuple(imp.module.split("."))
            # Verify chain prefix == module_parts.
            if len(chain) <= len(module_parts):
                return None
            for idx, mp in enumerate(module_parts):
                if chain[idx] != mp:
                    return None
            sub = chain[len(module_parts) :]
            if not sub:
                return None
            module = ".".join([imp.module, *sub[:-1]])
            var = sub[-1]
        else:
            # Case D: ``import x.y as alias``; head=alias, rest=(...,var)
            if not rest:
                return None
            module = ".".join([imp.module, *rest[:-1]])
            var = rest[-1]
    else:
        return None

    target_file = _module_to_file(module)
    if target_file is None:
        return None
    target_info = file_info_map.get(target_file)
    if target_info is None:
        return None
    if var in target_info.local_routers:
        return (target_file, var)
    # Re-export chain: the target file may itself import this name and
    # forward it on.
    if var in target_info.imports:
        return _resolve_chain(target_info, (var,), file_info_map, seen=seen)
    return None


def _prefix_signals_in_scope(prefix: str | None) -> bool:
    """Return True when *prefix* should pull the router into the trust scope.

    Two paths to True: a literal that mentions ``/extensions`` (the
    obvious case the guard targets), or :data:`_UNRESOLVABLE_PREFIX` --
    the sentinel returned for dynamic prefixes
    (``prefix=f"/extensions/{tenant}"``, ``prefix=PREFIX_VAR``) where we
    cannot prove the prefix isn't extension-targeted.  Treating
    unresolvable prefixes as in-scope keeps defense-in-depth honest.
    """
    if prefix is None:
        return False
    if prefix == _UNRESOLVABLE_PREFIX:
        return True
    return "/extensions" in prefix


def compute_in_scope(file_info_map: dict[Path, FileInfo]) -> set[RouterId]:
    in_scope: set[RouterId] = set()

    # Seed: APIRouter(prefix=".../extensions...") or prefix=<unresolvable>
    for path, info in file_info_map.items():
        for var, prefix in info.local_routers.items():
            if _prefix_signals_in_scope(prefix):
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
                child_id = _resolve_chain(info, call.child_chain, file_info_map)
                if child_id is None or child_id in in_scope:
                    continue
                child_in_scope = False
                if _prefix_signals_in_scope(call.child_prefix):
                    child_in_scope = True
                else:
                    parent_id = _resolve_chain(info, call.parent_chain, file_info_map)
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
    """Walk every decorator and flag forbidden handlers on in-scope routers.

    A decorator's router reference is a dotted chain (e.g.
    ``("router",)`` for ``@router.post(...)`` or ``("child", "api", "router")``
    for ``@child.api.router.post(...)``).  We resolve the chain back to a
    ``RouterId`` and check whether that router is in scope.
    """
    violations: list[str] = []

    for path, info in file_info_map.items():
        check_all = info.has_marker
        for deco in info.decorators:
            in_scope_router = check_all
            if not in_scope_router:
                deco_router = _resolve_chain(info, deco.router_chain, file_info_map)
                in_scope_router = deco_router is not None and deco_router in in_scope
            if not in_scope_router:
                continue
            token = _violation_token(deco.path) or _violation_token(deco.func_name)
            if token is not None:
                router_repr = ".".join(deco.router_chain)
                violations.append(
                    f"{path}:{deco.lineno}: forbidden token {token!r} in handler "
                    f"@{router_repr}.{deco.method}({deco.path!r}) def {deco.func_name}(...)"
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

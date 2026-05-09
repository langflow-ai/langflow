#!/usr/bin/env python3
"""CI guard: forbid install/uninstall/registry-mutation routes under /api/v1/extensions/**.

Per the Extension System trust boundary (Bundle Separation: Developer
Guide, section 4): "Install / uninstall / registry mutation never happens
at runtime on a live production server.  The router-trust CI guard in
LE-1017 enforces this: any handler under ``/api/v1/extensions/**``
matching install, uninstall, registry_add, or registry_remove fails CI."

This script statically scans the extensions API source files for
FastAPI route handlers whose path or function name contains a forbidden
verb.  It is intentionally simple -- regex over the route decorator and
function name -- so a reviewer can audit it in one pass.

Files scanned:
    src/backend/base/langflow/api/v1/extensions.py
    src/lfx/src/lfx/extension/  (any module that registers /api/v1/extensions
                                 routes via APIRouter; reserved for future
                                 modules)

Forbidden tokens (kebab- and snake-case both):
    install, uninstall, registry-add, registry_add,
    registry-remove, registry_remove

Exit codes:
    0 -- no forbidden routes
    1 -- forbidden route found (details to stderr)
    2 -- usage / IO error
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]

# Roots to scan recursively.  Any ``.py`` file under these roots that
# declares an ``APIRouter(prefix=...)`` whose prefix mounts under
# ``/extensions`` is checked.  This is broader than a hard-coded file list
# so a future PR that splits the extensions HTTP surface across multiple
# modules cannot bypass the guard by introducing a new file.
SCAN_ROOTS: tuple[Path, ...] = (
    REPO_ROOT / "src" / "backend" / "base" / "langflow" / "api",
    REPO_ROOT / "src" / "lfx" / "src" / "lfx",
)

# A router is "in scope" if its prefix string contains ``/extensions``.
# Detected via a substring match against the literal in the
# ``APIRouter(prefix="...")`` call.
ROUTER_PREFIX_RE = re.compile(
    r"APIRouter\([^)]*prefix\s*=\s*['\"]([^'\"]*?/?extensions[^'\"]*?)['\"]",
    re.DOTALL,
)
# An app-level mount with the same prefix string also counts (used by
# ``app.include_router(... prefix=...)`` and direct ``@app.post`` chains).
APP_INCLUDE_RE = re.compile(
    r"include_router\([^)]*prefix\s*=\s*['\"]([^'\"]*?/?extensions[^'\"]*?)['\"]",
    re.DOTALL,
)

# Forbidden tokens.  We match both naming conventions because route paths
# are kebab-case (``/install``) and function names are snake_case
# (``install_extension``).  The router-trust invariant covers both.
FORBIDDEN_TOKENS: tuple[str, ...] = (
    "install",
    "uninstall",
    "registry_add",
    "registry-add",
    "registry_remove",
    "registry-remove",
)

# A handful of identifiers contain forbidden tokens but do not register
# mutation verbs -- e.g. ``installed_extension_immutable`` is the typed
# error code raised when someone *tries* to mutate an installed extension.
# Allowlist these by exact substring so the guard can stay simple.
ALLOWED_SUBSTRINGS: tuple[str, ...] = (
    "installed-extension-immutable",
    "installed_extension_immutable",
    "_uninstall_immutable",  # reserved for the typed-error code namespace
)

# FastAPI route decorators we recognise.
ROUTE_DECORATOR_RE = re.compile(
    r"@(?:router|app)\.(?:get|post|put|patch|delete|options|head)\s*\(",
)
DEF_RE = re.compile(r"^\s*(?:async\s+)?def\s+(\w+)\s*\(")


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------


def _line_violates(line: str) -> str | None:
    """Return the forbidden token found in *line*, or ``None`` if clean."""
    lowered = line.lower()
    for allowed in ALLOWED_SUBSTRINGS:
        # Strip allowlisted substrings before scanning so the typed-error
        # code namespace does not trip the guard.
        lowered = lowered.replace(allowed, "")
    for token in FORBIDDEN_TOKENS:
        if token in lowered:
            return token
    return None


def file_is_in_scope(src: str) -> bool:
    """Return True if *src* declares or mounts a router under ``/extensions``.

    The check is best-effort textual: we trust authors not to obfuscate a
    forbidden route by computing the prefix at runtime.  Any future
    refactor that introduces a non-literal prefix should add an
    ``# router-trust: in-scope`` marker (a tag-line check is in
    ``_explicit_in_scope`` below).
    """
    if ROUTER_PREFIX_RE.search(src):
        return True
    if APP_INCLUDE_RE.search(src):
        return True
    return "# router-trust: in-scope" in src


def scan_file(path: Path) -> list[str]:
    """Return a list of human-readable violations found in *path*."""
    if not path.exists():
        # Missing file is not a violation; the guard's job is to catch new
        # routes, not to require the API module to exist.
        return []

    src = path.read_text(encoding="utf-8")
    if not file_is_in_scope(src):
        # Module exists but registers no /extensions routes; nothing to check.
        return []

    violations: list[str] = []
    lines = src.splitlines()

    in_decorator = False
    decorator_path: str = ""

    for lineno, raw in enumerate(lines, start=1):
        line = raw.strip()

        if ROUTE_DECORATOR_RE.search(line):
            in_decorator = True
            decorator_path = line
            # Decorator may span multiple lines; capture path argument from
            # the next few lines until we see the closing paren.
            continue

        if in_decorator:
            decorator_path += " " + line
            if ")" in line:
                in_decorator = False
                # Now decorator_path holds the full multi-line decorator.
                token = _line_violates(decorator_path)
                if token is not None:
                    violations.append(
                        f"{path}:{lineno}: forbidden token {token!r} in route decorator: {decorator_path[:160]}"
                    )

        match = DEF_RE.match(raw)
        if match:
            func_name = match.group(1)
            token = _line_violates(func_name)
            if token is not None:
                violations.append(f"{path}:{lineno}: forbidden token {token!r} in handler name: def {func_name}(...)")

    return violations


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def discover_paths(roots: tuple[Path, ...]) -> list[Path]:
    """Walk every ``.py`` file under ``roots`` (skipping caches)."""
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

    all_violations: list[str] = []
    for path in targets:
        all_violations.extend(scan_file(path))

    if all_violations:
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
        for violation in all_violations:
            print(f"  - {violation}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

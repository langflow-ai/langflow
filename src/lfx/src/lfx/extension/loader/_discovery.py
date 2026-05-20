"""Filesystem walk + module import for the extension loader.

This module owns the "find files / build module names / actually import"
half of the loader pipeline.  It deliberately knows nothing about Component
subclasses, manifests, or slot semantics -- those concerns live in
``_detection`` and ``_orchestrator`` respectively.  Keeping the layers
separate makes each file readable on its own and makes it cheap to swap in
an alternate import strategy (e.g. a cached / pre-bytecoded path) later
without touching the orchestration logic.
"""

from __future__ import annotations

import importlib.util
import sys
from typing import TYPE_CHECKING

from lfx.extension._paths import SKIP_DIR_NAMES, is_within
from lfx.extension.errors import ExtensionError

if TYPE_CHECKING:
    import types
    from collections.abc import Iterator
    from pathlib import Path


# ---------------------------------------------------------------------------
# Walk-skip lists
# ---------------------------------------------------------------------------

# Files we never treat as bundle modules.  Test scaffolding and dunder
# packaging files are intentionally excluded so a bundle's tests/ directory
# does not surface as half a dozen junk components.
SKIP_FILE_NAMES: frozenset[str] = frozenset({"__init__.py", "__main__.py", "conftest.py"})

# Re-export the shared SKIP_DIR_NAMES for backward-compat at this import path.
__all__ = [
    "DEFAULT_MODULE_NAMESPACE",
    "SKIP_DIR_NAMES",
    "SKIP_FILE_NAMES",
    "import_bundle_module",
    "iter_bundle_python_files",
    "module_name_for",
]


# ---------------------------------------------------------------------------
# Walk
# ---------------------------------------------------------------------------


def iter_bundle_python_files(bundle_root: Path) -> Iterator[Path]:
    """Yield every .py file under ``bundle_root`` in deterministic order.

    Symlinks are followed only if they stay inside ``bundle_root`` (the
    validate pass already guards this for static analysis; we re-check at
    load time to catch symlinks introduced after validate).

    ``bundle_root`` has already been resolved + existence-checked by the
    orchestrator's path-resolver; we use ``strict=False`` here so a
    concurrent removal in the narrow window between the two calls produces
    an empty walk rather than an unexpected ``FileNotFoundError`` escaping
    the loader's public boundary.
    """

    # Sort sibling directories and files at every level for platform-independent
    # walk order.  ``Path.iterdir`` order is filesystem-dependent.
    def _walk(current: Path) -> Iterator[Path]:
        try:
            children = sorted(current.iterdir(), key=lambda p: p.name)
        except OSError:
            return
        files: list[Path] = []
        dirs: list[Path] = []
        for child in children:
            if not is_within(child, bundle_root):
                # Symlink escapes the bundle; skip it entirely.
                continue
            if child.is_dir():
                if child.name in SKIP_DIR_NAMES:
                    continue
                dirs.append(child)
            elif child.is_file() and child.suffix == ".py" and child.name not in SKIP_FILE_NAMES:
                files.append(child)
        yield from files
        for directory in dirs:
            yield from _walk(directory)

    yield from _walk(bundle_root)


# ---------------------------------------------------------------------------
# Module name + import
# ---------------------------------------------------------------------------


DEFAULT_MODULE_NAMESPACE: str = "_lfx_ext"
"""Default top-level package name for bundle modules in ``sys.modules``.

Reload overrides this with ``__reload_staging__.<reload_id>`` so a
parallel load lands in an isolated namespace and Stage 3 can swap it in
atomically without ever touching the live modules.
"""


def module_name_for(
    file_path: Path,
    bundle_root: Path,
    bundle_name: str,
    slot: str,
    namespace: str = DEFAULT_MODULE_NAMESPACE,
) -> str:
    """Build a stable, collision-resistant module name for a bundle file.

    Shape: ``<namespace>.<slot>.<bundle>.<dotted relative path without .py>``.
    With the default namespace this is ``_lfx_ext.<slot>.<bundle>.<dotted>``;
    the leading underscore-prefixed package keeps these out of the regular
    import namespace so a bundle named ``json`` doesn't shadow the stdlib.
    Reload supplies a ``__reload_staging__.<id>`` namespace so Stage 1 lands
    in an isolated subtree of ``sys.modules``.
    """
    rel = file_path.relative_to(bundle_root).with_suffix("")
    dotted = ".".join(rel.parts)
    return f"{namespace}.{slot}.{bundle_name}.{dotted}"


def import_bundle_module(module_name: str, file_path: Path) -> tuple[types.ModuleType | None, ExtensionError | None]:
    """Import a single .py file as a module under ``module_name``.

    Returns ``(module, None)`` on success or ``(None, error)`` on failure.
    Errors are typed as ``module-import-failed``.
    """
    try:
        spec = importlib.util.spec_from_file_location(module_name, file_path)
    except (ValueError, ImportError, OSError) as exc:
        return None, ExtensionError(
            code="module-import-failed",
            message=f"Could not build module spec: {exc}",
            location=str(file_path),
            content=str(file_path),
            hint="Make sure the file path is readable and ends in .py.",
        )
    if spec is None or spec.loader is None:
        return None, ExtensionError(
            code="module-import-failed",
            message="Module spec could not be created",
            location=str(file_path),
            content=str(file_path),
            hint="Confirm that the path points at a regular .py file.",
        )
    module = importlib.util.module_from_spec(spec)
    # Single-load-per-process contract: this assignment overwrites any prior
    # entry under the same synthetic ``_lfx_ext.<slot>.<bundle>...`` name
    # with no cleanup. Consumers holding a previous LoadedComponent.klass
    # keep the old class object across reloads, so isinstance checks against
    # newly-loaded instances will return False. The reload pipeline owns
    # the invalidation: it must scrub registry entries (and the matching
    # ``_lfx_ext.<slot>.<bundle>.*`` sys.modules namespace) before calling
    # back into this loader. Absolute imports only between bundle modules;
    # relative imports unsupported.
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException as exc:  # noqa: BLE001
        # Deliberately broad: a bundle's top-level code may raise SystemExit,
        # KeyboardInterrupt, or any other BaseException subclass. At server
        # startup we want one bad bundle to surface as a typed error rather
        # than abort the whole loader pass. Re-raising the user's interrupt
        # is the wrong choice here because the loader runs before the user
        # has any way to drive interruption; the trade-off is intentional.
        # Roll back the optimistic sys.modules entry on failure so a retry
        # does not pick up a half-initialized module.
        sys.modules.pop(module_name, None)
        return None, ExtensionError(
            code="module-import-failed",
            message=f"{type(exc).__name__}: {exc}",
            location=str(file_path),
            content=str(file_path),
            hint=("Fix the import-time error in this module, or move the offending logic into a function body."),
        )
    return module, None

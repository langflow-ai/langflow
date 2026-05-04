"""Single-Bundle loader for the Langflow Extension System (LE-1015).

This module turns a directory tree on disk (an Extension or a loose
LANGFLOW_COMPONENTS_PATH entry) into a list of :class:`LoadedComponent`
records keyed by the namespaced ID ``ext:<bundle>:<Class>@<slot>``.

Two entry points exist:

    1. :func:`load_extension` -- given a directory containing a v0 manifest
       (extension.json or [tool.langflow.extension] in pyproject.toml), walk
       the bundle directory it declares, import each module, collect every
       :class:`Component` subclass, and register them at the ``official``
       slot.  Multi-bundle manifests are rejected here a second time (the
       schema rejects them too; the loader re-checks at runtime).

    2. :func:`discover_inline_bundles` -- given a list of LANGFLOW_COMPONENTS_PATH
       directories, treat each immediate subfolder as a Bundle at the
       ``extra`` slot.  Walk order is platform-independent: paths are
       iterated in user-declared order, subfolders within a path are sorted
       lexicographically.  Duplicate-name detection emits
       ``duplicate-inline-bundle`` warnings.

The loader's contract with the rest of the system is:

    - Bundle code is *trusted* (it was installed by pip or placed on the
      filesystem by the operator); we DO import it in-process.  This is the
      load-time analogue of validate's --execute-imports flag.  Sandboxing
      is out of scope for v0; the Extension System threat model is "the
      operator chose to install this".
    - Module discovery is recursive and deterministic.  Files are scanned
      in sorted order so the resulting registry order does not depend on
      the underlying filesystem.
    - Failures are typed.  Every error path produces an
      :class:`~lfx.extension.errors.ExtensionError`; nothing raises across
      the loader's public boundary except programmer errors (``TypeError``
      on a non-Path argument, etc.).

This file implements module discovery, import, and Component-class collection.
Discovery of *installed* extension distributions (the read-only @official
slot for pip-installed bundles) is owned by LE-1022.  The bridge function
:func:`installed_extension_roots` is provided here for LE-1015's
manifest-first precedence test (a distribution that ships a manifest has
its ``langflow.plugins`` component entry-points ignored); LE-1022 will
extend it with seed-directory discovery and CLI plumbing.
"""

from __future__ import annotations

import importlib.util
import inspect
import json
import re
import sys
from dataclasses import dataclass, field
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from lfx.extension.errors import ExtensionError
from lfx.extension.manifest import (
    _BUNDLE_NAME_RE,
    BundleRef,
    ExtensionManifest,
    load_manifest,
)

if TYPE_CHECKING:
    import types
    from collections.abc import Iterable, Iterator

# ---------------------------------------------------------------------------
# Slot names
# ---------------------------------------------------------------------------

SLOT_OFFICIAL: Literal["official"] = "official"
"""Slot for installed Extensions (pip install / manifest-shipping distribution)."""

SLOT_EXTRA: Literal["extra"] = "extra"
"""Slot for loose LANGFLOW_COMPONENTS_PATH directories (ad-hoc local dev)."""

_SLOT_VALUES: tuple[str, ...] = (SLOT_OFFICIAL, SLOT_EXTRA)


# ---------------------------------------------------------------------------
# Distribution-name normalization (PEP 503)
# ---------------------------------------------------------------------------

_PEP503_NORMALIZE_RE = re.compile(r"[-_.]+")


def _canonicalize_distribution(name: str) -> str:
    """Canonicalize a distribution name per PEP 503 (lowercase + collapse [-_.])."""
    return _PEP503_NORMALIZE_RE.sub("-", name).lower()


# ---------------------------------------------------------------------------
# LoadedComponent / LoadResult
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LoadedComponent:
    """A successfully loaded Component class plus its registry coordinates.

    Frozen so callers can place these in sets / dicts and emit them across
    the events pipeline (LE-1017) without worrying about mutation.

    The :attr:`namespaced_id` is the canonical address used by saved flows
    after the migration table (LE-1020) rewrites legacy references.
    """

    extension_id: str
    extension_version: str
    bundle: str
    class_name: str
    slot: Literal["official", "extra"]
    klass: type
    module_name: str
    file_path: Path
    distribution: str | None = None
    """Canonical PEP-503 distribution name when loaded from an installed
    package; ``None`` for inline LANGFLOW_COMPONENTS_PATH bundles."""

    @property
    def namespaced_id(self) -> str:
        """The ``ext:<bundle>:<Class>@<slot>`` registry address."""
        return f"ext:{self.bundle}:{self.class_name}@{self.slot}"


@dataclass
class LoadResult:
    """Outcome of a single load_extension or inline-bundle load.

    ``components`` is the registry payload on success; ``errors`` carries
    typed failures.  ``ok`` is the single bit downstream code should branch
    on (e.g. the events pipeline emits ``extension_loaded`` when ``ok`` and
    ``extension_error`` otherwise).

    ``extension_id`` and ``bundle`` are populated whenever the manifest /
    bundle-name was resolved, even if a later failure prevented full load.
    This lets the events pipeline attribute failures to a specific source
    (the AC: "load results carry extension_id and fix-hint payload on
    failure").
    """

    components: list[LoadedComponent] = field(default_factory=list)
    errors: list[ExtensionError] = field(default_factory=list)
    warnings: list[ExtensionError] = field(default_factory=list)
    extension_id: str | None = None
    extension_version: str | None = None
    bundle: str | None = None
    slot: Literal["official", "extra"] | None = None
    source_path: Path | None = None
    distribution: str | None = None

    @property
    def ok(self) -> bool:
        return not self.errors

    def __bool__(self) -> bool:  # pragma: no cover - convenience
        return self.ok


# ---------------------------------------------------------------------------
# Module discovery + import
# ---------------------------------------------------------------------------

# Files we never treat as bundle modules.  Test scaffolding and dunder
# packaging files are intentionally excluded so a bundle's tests/ directory
# does not surface as half a dozen junk components.
_SKIP_FILE_NAMES: frozenset[str] = frozenset({"__init__.py", "__main__.py", "conftest.py"})

# Directory names skipped during the recursive walk.  Same intent.
_SKIP_DIR_NAMES: frozenset[str] = frozenset({"__pycache__", ".git", ".venv", "venv", "node_modules", ".pytest_cache"})


def _iter_bundle_python_files(bundle_root: Path) -> Iterator[Path]:
    """Yield every .py file under ``bundle_root`` in deterministic order.

    Symlinks are followed only if they stay inside ``bundle_root`` (the
    validate pass already guards this for static analysis; we re-check at
    load time to catch symlinks introduced after validate).

    ``bundle_root`` has already been resolved + existence-checked by
    :func:`_resolve_bundle_path`; we use ``strict=False`` here so a
    concurrent removal in the narrow window between the two calls produces
    an empty walk rather than an unexpected ``FileNotFoundError`` escaping
    the loader's public boundary.
    """
    bundle_resolved = bundle_root.resolve(strict=False)

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
            try:
                resolved = child.resolve(strict=False)
                resolved.relative_to(bundle_resolved)
            except (OSError, ValueError):
                # Symlink escapes the bundle; skip it entirely.
                continue
            if child.is_dir():
                if child.name in _SKIP_DIR_NAMES:
                    continue
                dirs.append(child)
            elif child.is_file() and child.suffix == ".py" and child.name not in _SKIP_FILE_NAMES:
                files.append(child)
        yield from files
        for directory in dirs:
            yield from _walk(directory)

    yield from _walk(bundle_root)


def _module_name_for(file_path: Path, bundle_root: Path, bundle_name: str, slot: str) -> str:
    """Build a stable, collision-resistant module name for a bundle file.

    Shape: ``_lfx_ext.<slot>.<bundle>.<dotted relative path without .py>``.
    The leading underscore-prefixed package keeps these out of the regular
    import namespace so a bundle named ``json`` doesn't shadow the stdlib.
    """
    rel = file_path.relative_to(bundle_root).with_suffix("")
    dotted = ".".join(rel.parts)
    return f"_lfx_ext.{slot}.{bundle_name}.{dotted}"


def _import_bundle_module(module_name: str, file_path: Path) -> tuple[types.ModuleType | None, ExtensionError | None]:
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
    # Install in sys.modules so absolute imports of this module from within
    # the bundle resolve.  Relative imports (``from .sibling import X``) are
    # NOT supported in v0: the intermediate package entries are not
    # registered as packages, so authors must use absolute references between
    # bundle modules until that lands in a later milestone.
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException as exc:  # noqa: BLE001 - surface every import-time failure
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


def _is_component_subclass(obj: object) -> bool:
    """Return True if ``obj`` is a Component subclass that should register.

    The check uses runtime MRO: a class registers iff one of its bases is
    named ``Component`` or ends with ``Component``.  This mirrors the AST
    heuristic in validate.py and avoids importing the real Component base
    here (the loader is part of lfx; importing the rich Component class
    pulls in graph/, vertex/, etc., which are not needed for registration).

    A class is skipped if it is named ``Component`` (or ends in ``Component``)
    AND has no class body beyond the inherited members -- this excludes the
    base classes themselves from registration when they happen to be
    re-exported by a bundle module.
    """
    if not inspect.isclass(obj):
        return False
    # Skip the Component base classes themselves.  We can't import them
    # here without pulling in the full lfx graph stack, so we use the same
    # name-based heuristic as validate.py and rely on the convention that
    # bundle classes have their own name (not literally ``Component``).
    if obj.__name__ in {"Component", "CustomComponent", "BaseComponent"}:
        return False
    for base in obj.__mro__[1:]:
        if base is object:
            continue
        if base.__name__ == "Component" or base.__name__.endswith("Component"):
            return True
    return False


def _collect_component_classes(module: types.ModuleType) -> list[type]:
    """Return Component subclasses defined or aliased in ``module``.

    We require the class's ``__module__`` to match the module under
    inspection so that re-imports (``from x import Foo``) do not double
    register.  Stable order: iteration order of ``vars(module)`` is the
    insertion order in the module's namespace (i.e. source order), which
    is deterministic for a given source file.
    """
    seen: list[type] = []
    seen_ids: set[int] = set()
    module_name = module.__name__
    for value in vars(module).values():
        if not _is_component_subclass(value):
            continue
        # Restrict to classes actually declared in this module to avoid
        # double-registering re-exported classes from another bundle file.
        if getattr(value, "__module__", None) != module_name:
            continue
        # Defensive: avoid duplicate references inside the same module
        # (e.g. ``Foo = Foo`` at the bottom of a file).
        if id(value) in seen_ids:
            continue
        seen.append(value)
        seen_ids.add(id(value))
    return seen


# ---------------------------------------------------------------------------
# Path-safety helpers
# ---------------------------------------------------------------------------


def _resolve_bundle_path(root: Path, bundle: BundleRef) -> tuple[Path | None, ExtensionError | None]:
    """Resolve ``bundle.path`` under ``root`` and verify it exists.

    The schema layer already rejects ``..`` and absolute paths syntactically;
    here we additionally enforce that the resolved path stays inside the
    extension root, catching post-validate symlink swaps.
    """
    candidate = root / bundle.path
    try:
        resolved = candidate.resolve(strict=False)
    except OSError as exc:
        return None, ExtensionError(
            code="path-escape",
            message=f"Could not resolve bundle path: {exc}",
            location=bundle.path,
            content=bundle.path,
            hint="Make sure the bundle path resolves to a directory under the manifest.",
        )

    root_resolved = root.resolve(strict=False)
    try:
        resolved.relative_to(root_resolved)
    except ValueError:
        return None, ExtensionError(
            code="path-escape",
            message=(
                f"Bundle path {bundle.path!r} resolves to {resolved}, which is "
                f"outside the extension root {root_resolved}."
            ),
            location=bundle.path,
            content=bundle.path,
            hint="Move the bundle directory inside the extension root.",
        )

    if not resolved.exists():
        return None, ExtensionError(
            code="bundle-path-not-found",
            message=f"Bundle path {bundle.path!r} does not exist.",
            location="bundles[].path",
            content=bundle.path,
            hint="Create the bundle directory or fix the manifest path.",
        )
    if not resolved.is_dir():
        return None, ExtensionError(
            code="bundle-path-not-found",
            message=f"Bundle path {bundle.path!r} is not a directory.",
            location="bundles[].path",
            content=bundle.path,
            hint="Point bundles[].path at a directory, not a file.",
        )
    return resolved, None


# ---------------------------------------------------------------------------
# Core load: a directory + identity tuple -> LoadResult
# ---------------------------------------------------------------------------


def _load_bundle_directory(
    *,
    bundle_root: Path,
    bundle_name: str,
    extension_id: str,
    extension_version: str,
    slot: Literal["official", "extra"],
    distribution: str | None,
    result: LoadResult,
) -> None:
    """Walk ``bundle_root``, import every .py file, register Component subclasses.

    Mutates ``result`` in place.  Empty bundles emit ``bundle-empty``.
    """
    files = list(_iter_bundle_python_files(bundle_root))
    if not files:
        result.errors.append(
            ExtensionError(
                code="bundle-empty",
                message=f"Bundle {bundle_name!r} contains no Python source files.",
                location=str(bundle_root),
                content=bundle_name,
                hint="Add at least one Python module declaring a Component subclass.",
            )
        )
        return

    # class_name -> first-seen LoadedComponent (for duplicate detection).
    seen_classes: dict[str, LoadedComponent] = {}
    found_any_component = False

    for file_path in files:
        module_name = _module_name_for(file_path, bundle_root, bundle_name, slot)
        module, import_error = _import_bundle_module(module_name, file_path)
        if import_error is not None:
            result.errors.append(import_error)
            continue

        for klass in _collect_component_classes(module):
            class_name = klass.__name__
            loaded = LoadedComponent(
                extension_id=extension_id,
                extension_version=extension_version,
                bundle=bundle_name,
                class_name=class_name,
                slot=slot,
                klass=klass,
                module_name=module.__name__,
                file_path=file_path,
                distribution=distribution,
            )
            existing = seen_classes.get(class_name)
            if existing is not None:
                result.errors.append(
                    ExtensionError(
                        code="duplicate-component-name",
                        message=(
                            f"Component class {class_name!r} declared twice in bundle "
                            f"{bundle_name!r}: first at {existing.file_path}, "
                            f"again at {file_path}."
                        ),
                        location=bundle_name,
                        content=class_name,
                        hint=("Rename one of the component classes; class names must be unique within a bundle."),
                    )
                )
                continue
            seen_classes[class_name] = loaded
            result.components.append(loaded)
            found_any_component = True

    if not found_any_component and not result.errors:
        # Only emit the "no Component subclass" error if no other failure
        # already explained why the bundle yielded nothing.
        result.errors.append(
            ExtensionError(
                code="no-component-subclass",
                message=(f"Bundle {bundle_name!r} has Python sources but no class appears to inherit from Component."),
                location=str(bundle_root),
                content=bundle_name,
                hint=("At least one module must declare a class whose base is Component (or ends with Component)."),
            )
        )


# ---------------------------------------------------------------------------
# Public entry point: load_extension
# ---------------------------------------------------------------------------


def load_extension(
    root: Path | str,
    *,
    slot: Literal["official", "extra"] = SLOT_OFFICIAL,
    distribution: str | None = None,
) -> LoadResult:
    """Load an Extension at ``root``.

    Args:
        root: Path to the extension directory (the directory containing the
            manifest, not the bundle itself).
        slot: Where to register the loaded components.  Defaults to
            ``official`` for installed packages and seed directories.  Pass
            ``extra`` only for ad-hoc local dev where the directory is laid
            out like an Extension but is being loaded from a loose path.
        distribution: PEP-503 canonical name of the distribution this
            Extension was installed from.  ``None`` for filesystem-only
            extensions (e.g. ``langflow extension dev`` against a working
            tree before pip install).

    Returns:
        A :class:`LoadResult`.  ``ok`` is False on any structural failure;
        partial loads (some files imported, others failed) yield ``ok``
        False with successfully-loaded components still listed.
    """
    if slot not in _SLOT_VALUES:
        msg = f"slot must be one of {_SLOT_VALUES!r}, got {slot!r}"
        raise ValueError(msg)

    root_path = Path(root).resolve()
    result = LoadResult(slot=slot, source_path=root_path, distribution=distribution)

    try:
        source = load_manifest(root_path)
    except FileNotFoundError as exc:
        result.errors.append(
            ExtensionError(
                code="manifest-not-found",
                message=str(exc),
                location=str(root_path),
                hint=(
                    "Create an extension.json at the extension root or add a "
                    "[tool.langflow.extension] section to pyproject.toml."
                ),
            )
        )
        return result
    except (ValueError, TypeError) as exc:
        result.errors.append(
            ExtensionError(
                code="manifest-invalid",
                message=str(exc),
                location=str(root_path),
                hint="Run `lfx extension validate` for a detailed report.",
            )
        )
        return result

    manifest: ExtensionManifest = source.manifest
    result.extension_id = manifest.id
    result.extension_version = manifest.version

    # Multi-bundle is rejected by the schema, but we re-check here because
    # the loader is the runtime gate; a forged manifest that bypassed the
    # schema layer would otherwise silently load only the first bundle.
    if len(manifest.bundles) > 1:
        result.errors.append(
            ExtensionError(
                code="multi-bundle-deferred-in-this-milestone",
                message=(
                    f"Extension {manifest.id!r} declares {len(manifest.bundles)} bundles; v0 accepts exactly one."
                ),
                location=str(source.path),
                hint=("Split each bundle into its own Extension distribution until multi-bundle support ships."),
            )
        )
        return result

    bundle = manifest.bundles[0]
    result.bundle = bundle.name

    bundle_root, path_error = _resolve_bundle_path(root_path, bundle)
    if path_error is not None or bundle_root is None:
        if path_error is not None:
            result.errors.append(path_error)
        return result

    _load_bundle_directory(
        bundle_root=bundle_root,
        bundle_name=bundle.name,
        extension_id=manifest.id,
        extension_version=manifest.version,
        slot=slot,
        distribution=distribution,
        result=result,
    )
    return result


# ---------------------------------------------------------------------------
# Public entry point: discover_inline_bundles (LANGFLOW_COMPONENTS_PATH)
# ---------------------------------------------------------------------------


# Inline-bundle metadata, optionally provided as ``bundle.json`` at the
# bundle's root.  Only ``version`` is read in v0; ``name`` is derived from
# the directory name and validated against _BUNDLE_NAME_RE so that the
# namespaced ID is well-formed.  This is intentionally a tiny shape; full
# manifest support belongs at the @official slot.
_INLINE_BUNDLE_DEFAULT_VERSION = "0.0.0"


def _read_inline_bundle_json(bundle_root: Path) -> dict[str, str]:
    """Read optional ``bundle.json`` from a LANGFLOW_COMPONENTS_PATH bundle.

    Best-effort: a malformed file yields the defaults plus a warning would
    be ideal, but inline bundles are dev-only and a malformed bundle.json
    silently falls back to defaults to keep the dev loop moving.  The CLI
    surface (``extension validate``) is the right place to lint these.
    """
    candidate = bundle_root / "bundle.json"
    if not candidate.is_file():
        return {}
    try:
        data = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {k: v for k, v in data.items() if isinstance(v, str)}


def discover_inline_bundles(
    paths: Iterable[Path | str] | None,
) -> list[LoadResult]:
    """Discover and load inline bundles from LANGFLOW_COMPONENTS_PATH.

    Each entry in ``paths`` is a parent directory; every immediate
    subdirectory is treated as a Bundle at the ``extra`` slot.  Walk order:
    the user-declared ``paths`` order is preserved, and within each path
    subdirectories are sorted lexicographically (so ``a/`` is loaded before
    ``b/`` regardless of the underlying filesystem).

    Duplicate-name handling: when a bundle name appears in two different
    ``paths`` entries, the first one wins and the second emits a typed
    warning (``duplicate-inline-bundle``).  The warning lives on the
    *second* result so the events pipeline can attribute it to the path
    that actually got skipped.

    Subdirectories whose names do not match the bundle-name pattern (e.g.
    ``__pycache__``, dirs starting with ``.``) are silently skipped without
    a result.  A directory that *looks* like an intended bundle (no leading
    dot, but invalid characters) emits ``inline-bundle-name-invalid`` so
    the developer is told why their bundle isn't loading.
    """
    results: list[LoadResult] = []
    if paths is None:
        return results

    seen_names: dict[str, Path] = {}
    for path in paths:
        path_obj = Path(path).resolve()
        if not path_obj.is_dir():
            # Silently skip non-existent paths; consistent with the existing
            # LANGFLOW_COMPONENTS_PATH resolver in services/settings/base.py
            # which only appends paths that exist.
            continue

        try:
            children = sorted(path_obj.iterdir(), key=lambda p: p.name)
        except OSError:
            continue

        for child in children:
            if not child.is_dir():
                continue
            name = child.name
            # Skip clearly-internal directories without surfacing an error.
            if name.startswith(".") or name in _SKIP_DIR_NAMES:
                continue
            result = LoadResult(slot=SLOT_EXTRA, source_path=child)

            if not _BUNDLE_NAME_RE.match(name):
                result.errors.append(
                    ExtensionError(
                        code="inline-bundle-name-invalid",
                        message=(
                            f"Inline bundle directory {name!r} (under {path_obj}) does "
                            "not match the bundle name pattern."
                        ),
                        location=str(child),
                        content=name,
                        hint=("Rename the directory to lowercase snake_case starting with a letter, 2-64 characters."),
                    )
                )
                results.append(result)
                continue

            if name in seen_names:
                result.bundle = name
                result.warnings.append(
                    ExtensionError(
                        code="duplicate-inline-bundle",
                        message=(f"Inline bundle {name!r} already loaded from {seen_names[name]}; skipping {child}."),
                        location=f"{seen_names[name]} -> {child}",
                        content=name,
                        hint=(
                            "Rename one of the bundle directories or remove it from "
                            "LANGFLOW_COMPONENTS_PATH; first-wins resolution will "
                            "become a hard error in a later release."
                        ),
                    )
                )
                results.append(result)
                continue

            seen_names[name] = child

            bundle_meta = _read_inline_bundle_json(child)
            extension_id = bundle_meta.get("id") or name
            extension_version = bundle_meta.get("version") or _INLINE_BUNDLE_DEFAULT_VERSION

            result.extension_id = extension_id
            result.extension_version = extension_version
            result.bundle = name

            _load_bundle_directory(
                bundle_root=child,
                bundle_name=name,
                extension_id=extension_id,
                extension_version=extension_version,
                slot=SLOT_EXTRA,
                distribution=None,
                result=result,
            )
            results.append(result)

    return results


# ---------------------------------------------------------------------------
# Manifest-first precedence over langflow.plugins entry-points
# ---------------------------------------------------------------------------


def _distribution_manifest_path(dist: importlib_metadata.Distribution) -> Path | None:
    """Locate an extension manifest shipped by ``dist``, if any.

    A wheel that ships ``extension.json`` as package data exposes it via
    ``Distribution.files``.  The pyproject form is detected via the same
    mechanism: build backends that wire ``[tool.langflow.extension]`` are
    expected to also install the rendered ``extension.json`` alongside.
    Pure-pyproject distributions without that wiring will not be detected
    here; they should ship ``extension.json`` for the loader to see them.

    Returns the absolute path to the manifest file, or ``None``.
    """
    files = dist.files
    if files is None:
        return None
    for relative in files:
        if relative.parts and relative.parts[-1] == "extension.json":
            try:
                located = Path(dist.locate_file(relative))
            except (OSError, ValueError):
                # ``locate_file`` may raise on unusual setups (e.g. namespace
                # packages without a concrete root); treat as "not found"
                # without breaking the rest of the scan.
                continue
            if located.is_file():
                return located
    return None


def _distribution_canonical_name(dist: importlib_metadata.Distribution) -> str | None:
    """Return the PEP-503-canonical name of a distribution, or ``None``."""
    try:
        raw = dist.metadata["Name"]
    except (KeyError, AttributeError):
        return None
    if not raw:
        return None
    return _canonicalize_distribution(raw)


def installed_extension_roots(
    distributions: Iterable[importlib_metadata.Distribution] | None = None,
) -> dict[str, Path]:
    """Map canonical distribution name -> extension root for installed manifests.

    Used by:
        - the loader, to invoke :func:`load_extension` on every installed
          bundle at server startup;
        - the entry-point bridge, to skip ``langflow.plugins`` registrations
          for distributions that ship a manifest (manifest-first precedence).

    Args:
        distributions: Override the distribution iterator (test seam).
            Defaults to ``importlib.metadata.distributions()``.

    Returns:
        Dict keyed by canonical distribution name; the value is the
        directory containing ``extension.json``.  When a single distribution
        ships more than one ``extension.json`` (atypical but not forbidden),
        the lexicographically-first manifest path wins for determinism.
    """
    if distributions is None:
        distributions = importlib_metadata.distributions()

    # Two distributions with the same canonical name (rare but possible in
    # broken venvs) are resolved by keeping the lexicographically-first
    # manifest path for determinism.  LE-1022 will surface the conflict as
    # a typed warning when it owns the startup-time discovery flow; in this
    # primitive we only return the resolved mapping, never an error.
    found: dict[str, tuple[Path, str]] = {}
    for dist in distributions:
        manifest_path = _distribution_manifest_path(dist)
        if manifest_path is None:
            continue
        canonical = _distribution_canonical_name(dist)
        if canonical is None:
            continue
        root = manifest_path.parent
        existing = found.get(canonical)
        if existing is None or str(manifest_path) < existing[1]:
            found[canonical] = (root, str(manifest_path))

    return {name: root for name, (root, _) in found.items()}


def manifest_owning_distributions(
    distributions: Iterable[importlib_metadata.Distribution] | None = None,
) -> frozenset[str]:
    """Return the set of canonical distribution names that ship a manifest.

    Callers of ``langflow.plugins`` entry-point loading should consult this
    set and skip any entry point whose distribution is in it: the manifest
    is the source of truth for those distributions' components, and loading
    them again via the legacy entry-point would double-register.

    Non-component entry-points (services, routes) on the same distribution
    are NOT affected by this filter; the caller's loop is responsible for
    distinguishing component entry-points from other kinds.
    """
    return frozenset(installed_extension_roots(distributions=distributions).keys())


def filter_plugin_entry_points(
    entry_points: Iterable[importlib_metadata.EntryPoint],
    *,
    skip: Iterable[str] | None = None,
) -> tuple[list[importlib_metadata.EntryPoint], list[importlib_metadata.EntryPoint]]:
    """Partition ``langflow.plugins`` entry-points by manifest precedence.

    Args:
        entry_points: Entry points from ``importlib.metadata.entry_points``.
        skip: Optional override of canonical distribution names to skip.
            When ``None``, defaults to :func:`manifest_owning_distributions`.

    Returns:
        ``(kept, skipped)``.  Callers should load ``kept`` via the legacy
        path and ignore ``skipped``; the manifest layer will load those
        distributions' components.

    The partition is stable: ordering of inputs is preserved within each
    output list.  Entry points whose owning distribution cannot be
    determined are kept (we err on the side of compatibility).
    """
    skip_set = frozenset(skip) if skip is not None else manifest_owning_distributions()

    kept: list[importlib_metadata.EntryPoint] = []
    skipped: list[importlib_metadata.EntryPoint] = []
    for ep in entry_points:
        dist = getattr(ep, "dist", None)
        if dist is None:
            kept.append(ep)
            continue
        canonical = _distribution_canonical_name(dist)
        if canonical is None:
            kept.append(ep)
            continue
        if canonical in skip_set:
            skipped.append(ep)
        else:
            kept.append(ep)
    return kept, skipped

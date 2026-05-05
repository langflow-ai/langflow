"""Load orchestration: turn a directory tree into a :class:`LoadResult`.

This module wires the discovery + detection layers together and exposes the
two public entry points the rest of Langflow consumes:

    - :func:`load_extension` for an installed Extension (or filesystem dev
      checkout) that ships a v0 manifest.  Loads at the ``official`` slot.
    - :func:`discover_inline_bundles` for ``LANGFLOW_COMPONENTS_PATH`` --
      every immediate subfolder of every path is one Bundle at the
      ``extra`` slot, with first-wins resolution across paths.

Path-safety, multi-bundle re-checks, duplicate-name detection, and the
``no-component-subclass`` / ``bundle-empty`` discriminants are all enforced
here.  The lower-level layers stay agnostic of those rules so they remain
easy to unit-test in isolation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from lfx.extension.errors import ExtensionError
from lfx.extension.loader._detection import collect_component_classes
from lfx.extension.loader._discovery import (
    SKIP_DIR_NAMES,
    import_bundle_module,
    iter_bundle_python_files,
    module_name_for,
)
from lfx.extension.loader._types import (
    SLOT_EXTRA,
    SLOT_OFFICIAL,
    SLOT_VALUES,
    LoadedComponent,
    LoadResult,
)
from lfx.extension.manifest import (
    BUNDLE_NAME_RE,
    BundleRef,
    ExtensionManifest,
    load_manifest,
)

if TYPE_CHECKING:
    from collections.abc import Iterable


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
    files = list(iter_bundle_python_files(bundle_root))
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
        module_name = module_name_for(file_path, bundle_root, bundle_name, slot)
        module, import_error = import_bundle_module(module_name, file_path)
        if import_error is not None:
            result.errors.append(import_error)
            continue

        for klass in collect_component_classes(module):
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
    if slot not in SLOT_VALUES:
        msg = f"slot must be one of {SLOT_VALUES!r}, got {slot!r}"
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
# the directory name and validated against BUNDLE_NAME_RE so that the
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
            if name.startswith(".") or name in SKIP_DIR_NAMES:
                continue
            result = LoadResult(slot=SLOT_EXTRA, source_path=child)

            if not BUNDLE_NAME_RE.match(name):
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

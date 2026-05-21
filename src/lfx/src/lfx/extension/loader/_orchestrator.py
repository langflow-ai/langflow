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

import hashlib
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from lfx.extension._paths import SKIP_DIR_NAMES, is_within
from lfx.extension.errors import ExtensionError
from lfx.extension.loader._detection import collect_component_classes
from lfx.extension.loader._discovery import (
    DEFAULT_MODULE_NAMESPACE,
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
    BUNDLE_API_VERSION,
    BUNDLE_NAME_RE,
    BundleRef,
    ExtensionManifest,
    load_manifest,
)

if TYPE_CHECKING:
    from collections.abc import Iterable


logger = logging.getLogger(__name__)


def _hash_file(path: Path) -> str:
    """Return SHA-256 hex digest of ``path`` bytes, or ``""`` on failure.

    Used to stamp :attr:`LoadedComponent.source_hash` so the reload diff can
    detect in-class body edits where the class-name set is unchanged.
    Read errors (permissions, race with deletion) degrade gracefully to an
    empty hash; the diff treats empty hashes as "unknown" and never reports
    them as changed, matching the prior behaviour for callers that bypass
    the orchestrator.
    """
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


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

    if not is_within(resolved, root):
        root_resolved = root.resolve(strict=False)
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
    module_namespace: str = DEFAULT_MODULE_NAMESPACE,
) -> None:
    """Walk ``bundle_root``, import every .py file, register Component subclasses.

    Mutates ``result`` in place.  Empty bundles emit ``bundle-empty``.

    ``module_namespace`` controls the top-level package name used in
    ``sys.modules``; see :func:`lfx.extension.loader._discovery.module_name_for`.
    """
    # Multi-file bundle partial-failure orphan policy:
    # If a bundle has files {A, B, C} and importing C raises, the per-module
    # rollback in ``_discovery.import_bundle_module`` (see lines 167-169
    # there) pops C from sys.modules, but A and B stay registered under
    # ``_lfx_ext.<slot>.<bundle>.{a,b}``.  This is deliberate: the reload
    # pipeline (lfx.extension.reload) re-stages the whole bundle under
    # ``__reload_staging__.<id>`` and is the layer that owns cleanup --
    # orphans get overwritten on the next successful reload.
    #
    # At server startup, however, there is no reload pipeline running.  A
    # bundle that fails partial import at boot leaves the earlier modules
    # in sys.modules until process restart, and any module-level side
    # effects they registered (hooks, sys.path patches) are durable.  The
    # contract is "best effort: surface the per-module error, leave the
    # process import-able"; operators are expected to fix the broken
    # source file and restart, not to lean on a startup-side sweep.
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
    # Track call-local failures so the no-component-subclass diagnostic stays
    # accurate when a future caller reuses a LoadResult (e.g. multi-bundle or
    # a batch wrapper) and the aggregate ``result.errors`` list already has
    # entries from a sibling call.
    call_local_errors_emitted = 0

    for file_path in files:
        module_name = module_name_for(file_path, bundle_root, bundle_name, slot, namespace=module_namespace)
        module, import_error = import_bundle_module(module_name, file_path)
        if import_error is not None:
            result.errors.append(import_error)
            call_local_errors_emitted += 1
            continue

        # Hash the file once per module so multi-class files don't re-read
        # disk for each class; failure to read leaves source_hash="" rather
        # than aborting the load (the hash is advisory for the reload diff).
        source_hash = _hash_file(file_path)

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
                source_hash=source_hash,
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
                call_local_errors_emitted += 1
                continue
            seen_classes[class_name] = loaded
            result.components.append(loaded)
            found_any_component = True

    if not found_any_component and call_local_errors_emitted == 0:
        # Only emit the "no Component subclass" error if no other failure
        # *from this call* already explained why the bundle yielded nothing.
        # Gating on the aggregate ``result.errors`` would silently drop this
        # diagnostic when a caller reuses a LoadResult.
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
    module_namespace: str = DEFAULT_MODULE_NAMESPACE,
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
        module_namespace: Top-level package name used when registering bundle
            modules in ``sys.modules``.  Defaults to ``_lfx_ext`` for normal
            loads.  The reload pipeline passes ``__reload_staging__.<id>``
            so Stage 1 lands in an isolated namespace; do not override
            this in normal application code.

    Returns:
        A :class:`LoadResult`.  ``ok`` is False on any structural failure;
        partial loads (some files imported, others failed) yield ``ok``
        False with successfully-loaded components still listed.

    Single-load-per-process contract:
        Calling this function a second time for the same bundle overwrites
        the prior bundle's entries in ``sys.modules`` with no cleanup;
        previously-issued :class:`LoadedComponent` ``klass`` references
        remain bound to the old class objects. The reload pipeline is
        responsible for scrubbing registry entries AND the matching
        ``_lfx_ext.<slot>.<bundle>.*`` namespace before re-invoking this
        loader; direct callers should not rely on this function to refresh
        already-loaded bundles.
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

    # Version-constraint check: the manifest's lfx.compat list must include
    # this lfx package's BUNDLE_API_VERSION.  A bundle declaring only
    # ``["2"]`` against a lfx that ships ``BUNDLE_API_VERSION=1`` would
    # otherwise import successfully and crash later when it touched a
    # contract surface that did not exist yet.  This is the runtime half
    # of the contract-version check; the validator surfaces malformed
    # entries earlier with ``manifest-invalid``.
    declared = list(manifest.lfx.compat)
    if str(BUNDLE_API_VERSION) not in declared:
        result.errors.append(
            ExtensionError(
                code="version-constraint-unsatisfied",
                message=(
                    f"Extension {manifest.id!r} declares lfx.compat={declared!r}, "
                    f"which does not include this lfx package's "
                    f"BUNDLE_API_VERSION={BUNDLE_API_VERSION!s}."
                ),
                location=str(source.path),
                content=str(declared),
                hint=(
                    f"Update the manifest's lfx.compat to include "
                    f'"{BUNDLE_API_VERSION!s}", or install a Langflow whose '
                    f"BUNDLE_API_VERSION matches the bundle's declared compat."
                ),
            )
        )
        return result

    # Multi-bundle is rejected by the schema, but we re-check here because
    # the loader is the runtime gate; a forged manifest that bypassed the
    # schema layer would otherwise silently load only the first bundle.
    if len(manifest.bundles) != 1:
        result.errors.append(
            ExtensionError(
                code="multi-bundle-unsupported",
                message=(
                    f"Extension {manifest.id!r} declares {len(manifest.bundles)} bundles; v0 accepts exactly one. "
                    "Multi-bundle support is deferred to a future milestone."
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
        module_namespace=module_namespace,
    )
    return result


# ---------------------------------------------------------------------------
# Public entry point: discover_inline_bundles (LANGFLOW_COMPONENTS_PATH)
# ---------------------------------------------------------------------------


# Inline-bundle metadata, optionally provided as ``bundle.json`` at the
# bundle's root.  Recognised keys in v0:
#   - ``id``: optional extension id; consumed by callers that need to
#     attribute components back to a stable identifier separate from the
#     directory name.  Validated against the same regex as the manifest
#     so a malformed id is rejected rather than silently corrupting the
#     registry's keying.
#   - ``version``: optional SemVer-ish string used for the bundle's
#     ``extension_version``; defaults to ``0.0.0``.
#   - ``name``: ignored; the bundle name is always derived from the
#     directory name and validated against BUNDLE_NAME_RE so that the
#     namespaced ID is well-formed.
# This is intentionally a tiny shape; full manifest support belongs at
# the @official slot.
_INLINE_BUNDLE_DEFAULT_VERSION = "0.0.0"


def _validate_inline_bundle_id(
    candidate: str,
    *,
    directory_name: str,
    location: str,
) -> tuple[str, ExtensionError | None]:
    """Validate ``bundle.json`` ``id`` against the extension-id pattern.

    Returns the id to use plus an optional typed warning.  A malformed
    candidate falls back to ``directory_name`` and emits a typed
    ``inline-bundle-name-invalid`` warning so the operator sees the
    misconfiguration in the diagnostics emitter instead of getting an
    obscure registry mismatch later.
    """
    from lfx.extension.manifest import _EXTENSION_ID_RE

    if _EXTENSION_ID_RE.fullmatch(candidate):
        return candidate, None
    return directory_name, ExtensionError(
        code="inline-bundle-name-invalid",
        message=(
            f"bundle.json id {candidate!r} does not match the extension-id pattern; "
            f"falling back to the directory name {directory_name!r}."
        ),
        location=location,
        content=candidate,
        hint="Use lowercase, hyphenated, starting with a letter, 2-64 chars.",
    )


def _read_inline_bundle_json(
    bundle_root: Path,
    *,
    result: LoadResult | None = None,
) -> dict[str, str]:
    """Read optional ``bundle.json`` from a LANGFLOW_COMPONENTS_PATH bundle.

    A malformed or non-object file falls back to derived defaults so the
    dev loop keeps moving (the CLI ``extension validate`` is the right
    place for an authoritative lint), but if a ``result`` is provided the
    misconfig is also surfaced as a typed ``bundle-json-invalid`` warning
    so a developer who typo'd JSON gets a working-looking bundle without
    silent identity rewrites.
    """
    candidate = bundle_root / "bundle.json"
    if not candidate.is_file():
        return {}

    def _warn(detail: str) -> None:
        if result is None:
            return
        result.warnings.append(
            ExtensionError(
                code="bundle-json-invalid",
                message=f"bundle.json at {candidate} ignored: {detail}",
                location=str(candidate),
                content=str(candidate),
                hint=(
                    "Fix the JSON syntax or the schema (top-level must be an object) "
                    "or remove bundle.json to use the directory-derived id/version."
                ),
            )
        )

    try:
        data = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.debug("Ignoring malformed bundle.json at %s: %s", candidate, exc)
        _warn(f"{type(exc).__name__}: {exc}")
        return {}
    if not isinstance(data, dict):
        logger.debug("Ignoring bundle.json at %s: top-level value is not an object", candidate)
        _warn("top-level value is not an object")
        return {}
    return {k: v for k, v in data.items() if isinstance(v, str)}


def load_inline_bundle(
    bundle_root: Path | str,
    *,
    module_namespace: str = DEFAULT_MODULE_NAMESPACE,
) -> LoadResult:
    """Load a single inline (@extra) bundle directly from its bundle directory.

    Mirrors the per-bundle subset of :func:`discover_inline_bundles`, but
    targets one already-known bundle directory instead of walking a parent
    LANGFLOW_COMPONENTS_PATH entry.  Used by the reload pipeline so a
    bundle whose live ``source_path`` is the bundle directory itself (the
    shape recorded for inline @extra bundles) can be reloaded without
    confusing it with a manifest root.

    Identity is derived from the directory name plus optional ``bundle.json``
    metadata, just like first-time discovery; the bundle name pattern is
    re-checked here so a forged record cannot resurrect a malformed bundle.
    """
    root = Path(bundle_root).resolve()
    result = LoadResult(slot=SLOT_EXTRA, source_path=root)

    if not root.is_dir():
        result.errors.append(
            ExtensionError(
                code="inline-path-missing",
                message=f"Inline bundle path {root} does not exist or is not a directory.",
                location=str(root),
                content=str(root),
                hint=("Restore the bundle directory or uninstall the bundle from the registry."),
            )
        )
        return result

    name = root.name
    if not BUNDLE_NAME_RE.match(name):
        result.errors.append(
            ExtensionError(
                code="inline-bundle-name-invalid",
                message=(f"Inline bundle directory {name!r} does not match the bundle name pattern."),
                location=str(root),
                content=name,
                hint=("Rename the directory to lowercase snake_case starting with a letter, 2-64 characters."),
            )
        )
        return result

    bundle_meta = _read_inline_bundle_json(root, result=result)
    raw_id = bundle_meta.get("id")
    if raw_id:
        extension_id, id_warning = _validate_inline_bundle_id(
            raw_id, directory_name=name, location=str(root / "bundle.json")
        )
        if id_warning is not None:
            result.warnings.append(id_warning)
    else:
        extension_id = name
    extension_version = bundle_meta.get("version") or _INLINE_BUNDLE_DEFAULT_VERSION

    result.extension_id = extension_id
    result.extension_version = extension_version
    result.bundle = name

    _load_bundle_directory(
        bundle_root=root,
        bundle_name=name,
        extension_id=extension_id,
        extension_version=extension_version,
        slot=SLOT_EXTRA,
        distribution=None,
        result=result,
        module_namespace=module_namespace,
    )
    return result


def discover_inline_bundles(
    paths: Iterable[Path | str] | None,
) -> list[LoadResult]:
    """Discover inline bundles from LANGFLOW_COMPONENTS_PATH at the @extra slot.

    First-wins on duplicate bundle names across paths; the loser emits a
    typed ``duplicate-inline-bundle`` warning.
    """
    results: list[LoadResult] = []
    if paths is None:
        return results

    seen_names: dict[str, Path] = {}
    for path in paths:
        path_obj = Path(path).resolve()
        if not path_obj.is_dir():
            # The settings layer also filters non-existent entries, but a
            # typo here would otherwise produce zero components and zero
            # diagnostics -- a tough debug experience. Surface a typed
            # warning per skipped path so the operator sees what got
            # ignored. The result has no bundle (we never identified one)
            # so the events pipeline emits this as a path-level diagnostic.
            missing_result = LoadResult(slot=SLOT_EXTRA, source_path=path_obj)
            missing_result.warnings.append(
                ExtensionError(
                    code="inline-path-missing",
                    message=(
                        f"LANGFLOW_COMPONENTS_PATH entry {path_obj} does not exist or is not a directory; skipped."
                    ),
                    location=str(path_obj),
                    content=str(path_obj),
                    hint=(
                        "Remove the path from LANGFLOW_COMPONENTS_PATH or create the "
                        "directory; the loader needs an existing parent dir to scan."
                    ),
                )
            )
            results.append(missing_result)
            continue

        try:
            children = sorted(path_obj.iterdir(), key=lambda p: p.name)
        except OSError as exc:
            # Permission denied / other directory-enumeration failure on a
            # user-configured path. The user explicitly pointed us here, so
            # silently swallowing the error would lose the message entirely;
            # surface a typed warning carrying str(exc) so an operator can
            # diagnose the misconfiguration.
            unreadable_result = LoadResult(slot=SLOT_EXTRA, source_path=path_obj)
            unreadable_result.errors.append(
                ExtensionError(
                    code="inline-path-unreadable",
                    message=f"{type(exc).__name__}: {exc}",
                    location=str(path_obj),
                    content=str(path_obj),
                    hint=("Check filesystem permissions on the path or remove it from LANGFLOW_COMPONENTS_PATH."),
                )
            )
            results.append(unreadable_result)
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
                        hint=("Rename one of the bundle directories or remove it from LANGFLOW_COMPONENTS_PATH."),
                    )
                )
                results.append(result)
                continue

            seen_names[name] = child

            bundle_meta = _read_inline_bundle_json(child, result=result)
            raw_id = bundle_meta.get("id")
            if raw_id:
                extension_id, id_warning = _validate_inline_bundle_id(
                    raw_id, directory_name=name, location=str(child / "bundle.json")
                )
                if id_warning is not None:
                    result.warnings.append(id_warning)
            else:
                extension_id = name
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


# load_installed_extensions / load_seed_extensions live in
# :mod:`lfx.extension.loader._startup` (extracted to keep this orchestration
# file under the structural file-size limit).  They are re-exported from
# the loader package so external imports are unchanged.

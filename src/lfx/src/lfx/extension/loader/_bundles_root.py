"""Manifest-less ``lfx.bundles`` discovery: folder-walk bundle roots at @official.

The third @official-slot production source, after installed-manifest bundles
(:func:`load_installed_extensions`) and seed-directory bundles
(:func:`load_seed_extensions`).  A distribution opts in by declaring::

    [project.entry-points."lfx.bundles"]
    lfx_bundles = "lfx_bundles"

The value is the importable package whose *immediate subdirectories* are each
a manifest-less bundle, registered at the @official slot and named after the
subdirectory.  This is the langchain-community model: no ``extension.json``,
no per-provider manifest -- a new provider is just a new folder.  These
directories are not inputs to ``lfx extension validate``: the validator
requires a manifest (``extension.json`` or ``[tool.langflow.extension]`` in
``pyproject.toml``) and reports ``manifest-not-found`` without one.

Discovery mirrors :func:`lfx.extension.loader._orchestrator.discover_inline_bundles`
(the @extra manifest-less folder walk for ``LANGFLOW_COMPONENTS_PATH``) but
sources its roots from the entry-point group instead of an env var and
registers at @official.

Precedence relative to the manifest sources (installed > seed) and the loose
sources (dev > inline) is resolved by
:func:`lfx.interface.components._resolve_bundle_shadowing`: **manifest always
wins**.  A graduated ``lfx-<provider>`` shipping ``extension.json`` therefore
shadows a same-named provider shipped here with a typed ``bundle-shadowed``
warning -- which is what lets a provider graduate out of the metapackage with
no lockstep release.

Failure policy
--------------
A declaration that cannot be resolved to a real package directory yields a
sentinel :class:`LoadResult` carrying a ``bundle-discovery-malformed``
*warning* (not an error), so a broken third-party declaration degrades to
"that bundle root is skipped" rather than aborting server startup.  The same
warning is emitted for a top-level entry whose name is not a valid bundle
name (e.g. a provider folder that was not lowercased), so the mistake is
visible instead of silently dropping the provider.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

from lfx.extension._paths import SKIP_DIR_NAMES, is_within
from lfx.extension.errors import ExtensionError
from lfx.extension.loader._orchestrator import _load_bundle_directory
from lfx.extension.loader._types import SLOT_OFFICIAL, LoadResult
from lfx.extension.manifest import BUNDLE_NAME_RE

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping
    from importlib import metadata as importlib_metadata

LFX_BUNDLES_ENTRY_POINT_GROUP = "lfx.bundles"
"""The setuptools entry-point group a distribution declares to register a
manifest-less bundle root."""

_DEFAULT_BUNDLE_VERSION = "0.0.0"
"""Stamped on records when the providing distribution's version cannot be
resolved (e.g. a working-tree import not yet pip-installed)."""

_MALFORMED_HINT = (
    'Fix the [project.entry-points."lfx.bundles"] declaration so its value is '
    "an importable package whose immediate subdirectories are bundles."
)


class _BundleRoot(NamedTuple):
    """A resolved manifest-less bundle root plus its providing-distribution identity.

    ``extension_id`` / ``extension_version`` are stamped onto every
    :class:`LoadedComponent` discovered under ``path`` for palette display and
    diagnostics; the component's registry address
    (``ext:<bundle>:<Class>@official``) does not depend on them.
    """

    path: Path
    extension_id: str
    extension_version: str


def load_lfx_bundles_extensions(
    *,
    entry_points: Iterable[importlib_metadata.EntryPoint] | None = None,
    claimed_bundles: Mapping[str, tuple[str, str]] | None = None,
) -> list[LoadResult]:
    """Discover manifest-less ``lfx.bundles`` roots and load them at @official.

    Iterates the ``lfx.bundles`` entry-point group (override via the
    ``entry_points`` test seam -- pass a pre-filtered iterable of entry points
    so resolution is exercised without the live environment), resolves each
    declared package to a directory, and folder-walks its immediate
    subdirectories -- each valid subdirectory is one manifest-less bundle at
    the @official slot.

    ``claimed_bundles`` maps bundle names already won by a higher-precedence
    @official source (installed > seed) to ``(source_kind, source_path)``.
    A provider directory whose name is claimed is **never imported** -- its
    result carries a typed ``bundle-shadowed`` warning instead.  Skipping the
    import (rather than letting :func:`_resolve_bundle_shadowing` drop the
    components afterwards) matters because all @official sources share the
    ``_lfx_ext.official.<bundle>.*`` sys.modules namespace: importing the
    losing copy would overwrite the winner's live modules.  This is the
    normal graduation state -- a manifest-shipping ``lfx-<provider>``
    installed alongside an older metapackage that still contains the same
    provider -- not an operator error.

    Returns one :class:`LoadResult` per discovered bundle, plus one sentinel
    :class:`LoadResult` carrying a ``bundle-discovery-malformed`` warning per
    declaration that could not be resolved.  Order is deterministic: entry
    points sorted by ``(name, value)``, subdirectories sorted by name.  The
    malformed sentinels come first so the diagnostics emitter surfaces them
    even when no valid bundle followed.
    """
    roots, sentinels = _resolve_bundle_roots(entry_points)
    return [*sentinels, *_load_bundle_roots(roots, claimed_bundles=claimed_bundles)]


def _resolve_bundle_roots(
    entry_points: Iterable[importlib_metadata.EntryPoint] | None,
) -> tuple[list[_BundleRoot], list[LoadResult]]:
    """Resolve ``lfx.bundles`` entry points to package directories.

    Returns ``(roots, sentinels)`` where ``roots`` are the resolvable bundle
    roots (sorted, deterministic) and ``sentinels`` are warning-only
    :class:`LoadResult` objects for declarations that failed to resolve.
    """
    if entry_points is None:
        from importlib import metadata as importlib_metadata

        entry_points = importlib_metadata.entry_points(group=LFX_BUNDLES_ENTRY_POINT_GROUP)

    roots: list[_BundleRoot] = []
    sentinels: list[LoadResult] = []
    ordered = sorted(
        entry_points,
        key=lambda ep: (getattr(ep, "name", "") or "", getattr(ep, "value", "") or ""),
    )
    for ep in ordered:
        module_name = (getattr(ep, "value", "") or "").split(":", 1)[0].strip()
        label = module_name or getattr(ep, "name", "") or "<unknown>"
        if not module_name:
            sentinels.append(
                _malformed_sentinel(label, "entry-point value is empty; expected an importable package name.")
            )
            continue
        # ``find_spec`` locates the package without importing it, so a
        # discovery pass at startup does not trigger arbitrary ``__init__``
        # side-effects -- the same discipline as ``_manifest_via_entry_point``.
        try:
            spec = importlib.util.find_spec(module_name)
        except (ImportError, ValueError, ModuleNotFoundError, AttributeError) as exc:
            sentinels.append(
                _malformed_sentinel(label, f"find_spec({module_name!r}) failed: {type(exc).__name__}: {exc}")
            )
            continue
        package_dir = _spec_package_dir(spec)
        if package_dir is None or not package_dir.is_dir():
            sentinels.append(
                _malformed_sentinel(label, f"module {module_name!r} does not resolve to a package directory.")
            )
            continue
        extension_id, extension_version = _distribution_identity(ep, fallback_id=module_name)
        roots.append(_BundleRoot(path=package_dir, extension_id=extension_id, extension_version=extension_version))
    return roots, sentinels


def _load_bundle_roots(
    roots: Iterable[_BundleRoot],
    *,
    claimed_bundles: Mapping[str, tuple[str, str]] | None = None,
) -> list[LoadResult]:
    """Folder-walk each resolved root, loading every valid subdirectory at @official.

    First-wins on duplicate bundle names across roots (the loser emits a typed
    ``bundle-shadowed`` warning); names in ``claimed_bundles`` (already won by
    a higher-precedence installed/seed source) are skipped *without importing*
    so the winner's ``_lfx_ext.official.<bundle>.*`` sys.modules entries are
    never overwritten.  Subdirectories whose name is not a valid bundle name
    emit ``bundle-discovery-malformed`` and are skipped.  Internal directories
    (dot-prefixed, underscore-prefixed, or in :data:`SKIP_DIR_NAMES`) are
    skipped silently -- they are package machinery, not providers.
    """
    claimed = claimed_bundles or {}
    results: list[LoadResult] = []
    seen_names: dict[str, Path] = {}
    for root in roots:
        try:
            children = sorted(root.path.iterdir(), key=lambda p: p.name)
        except OSError as exc:
            # The resolver confirmed the directory existed, but a race or
            # permission change could still fail enumeration. Surface it
            # rather than aborting the whole discovery pass.
            sentinel = LoadResult(slot=None, source_path=root.path)
            sentinel.warnings.append(
                _malformed_error(str(root.path), f"could not enumerate bundle root: {type(exc).__name__}: {exc}")
            )
            results.append(sentinel)
            continue

        for child in children:
            if not child.is_dir():
                continue
            name = child.name
            if name.startswith((".", "_")) or name in SKIP_DIR_NAMES:
                continue
            # Same containment rule as the seed-directory walk: a symlinked
            # provider directory that resolves outside the bundle root is not
            # loaded.  The file-level walk inside _load_bundle_directory checks
            # containment against the (possibly symlinked-out) child itself,
            # so this directory-level check is what anchors the trust boundary
            # to the installed package tree.
            if not is_within(child, root.path):
                result = LoadResult(slot=None, source_path=child)
                result.warnings.append(
                    _malformed_error(
                        name,
                        f"provider directory {name!r} resolves outside the bundle root {root.path}; skipped.",
                        location=str(child),
                    )
                )
                results.append(result)
                continue

            result = LoadResult(slot=SLOT_OFFICIAL, source_path=child, manifestless=True)

            if not BUNDLE_NAME_RE.match(name):
                result.warnings.append(
                    _malformed_error(
                        name,
                        f"provider directory {name!r} (under {root.path}) is not a valid bundle "
                        "name; lowercase snake_case (a-z, 0-9, _), 2-64 characters.",
                        location=str(child),
                    )
                )
                results.append(result)
                continue

            if name in claimed:
                winner_kind, winner_path = claimed[name]
                result.bundle = name
                result.warnings.append(
                    ExtensionError(
                        code="bundle-shadowed",
                        message=(
                            f"Manifest-less bundle {name!r} at {child} is shadowed by a "
                            f"higher-precedence source at {winner_path} (source: {winner_kind}); "
                            "the metapackage copy is not imported."
                        ),
                        location=str(child),
                        content=name,
                        hint=(
                            "Discovery precedence is installed > seed > lfx_bundles > dev > inline. "
                            "This is expected after a provider graduates to a standalone "
                            "lfx-<provider> package; upgrade the metapackage to a version without "
                            "this provider to silence the warning."
                        ),
                    )
                )
                results.append(result)
                continue

            if name in seen_names:
                result.bundle = name
                result.warnings.append(
                    ExtensionError(
                        code="bundle-shadowed",
                        message=(
                            f"Manifest-less bundle {name!r} already discovered from {seen_names[name]}; "
                            f"skipping the copy at {child}."
                        ),
                        location=f"{seen_names[name]} -> {child}",
                        content=name,
                        hint=(
                            "A provider name must come from exactly one lfx.bundles root; rename or "
                            "remove the duplicate provider directory."
                        ),
                    )
                )
                results.append(result)
                continue

            seen_names[name] = child
            result.extension_id = root.extension_id
            result.extension_version = root.extension_version
            result.bundle = name
            _load_bundle_directory(
                bundle_root=child,
                bundle_name=name,
                extension_id=root.extension_id,
                extension_version=root.extension_version,
                slot=SLOT_OFFICIAL,
                # Manifest-less roots are NOT the installed-manifest tier; a
                # ``None`` distribution keeps any distribution-keyed logic from
                # mistaking them for a pip-installed Extension. @official +
                # distribution=None is permitted (see LoadedComponent).
                distribution=None,
                result=result,
            )
            results.append(result)

    return results


def _spec_package_dir(spec: importlib.machinery.ModuleSpec | None) -> Path | None:
    """Return the package directory a module spec points at, or ``None``.

    Only package specs qualify (``submodule_search_locations`` is set for both
    regular and namespace packages, and equals the package directory).  A
    plain-module spec returns ``None`` -- a single-file module has no provider
    subdirectories, and falling back to the module file's parent would
    folder-walk unrelated sibling directories as bundles.
    """
    if spec is None:
        return None
    locations = list(spec.submodule_search_locations or [])
    if locations:
        return Path(locations[0])
    return None


def _distribution_identity(
    ep: importlib_metadata.EntryPoint,
    *,
    fallback_id: str,
) -> tuple[str, str]:
    """Resolve ``(extension_id, extension_version)`` from the entry point's distribution.

    Uses the providing distribution's canonical name + version when available
    (so the palette shows e.g. ``lfx-bundles 1.0.0``); falls back to the
    module name and :data:`_DEFAULT_BUNDLE_VERSION` for working-tree imports
    that are not pip-installed.
    """
    dist = getattr(ep, "dist", None)
    if dist is None:
        return fallback_id, _DEFAULT_BUNDLE_VERSION
    name = getattr(dist, "name", None)
    if not name:
        try:
            name = dist.metadata["Name"]
        except (KeyError, AttributeError, TypeError):
            name = None
    version = getattr(dist, "version", None)
    return name or fallback_id, version or _DEFAULT_BUNDLE_VERSION


def _malformed_error(content: str, message: str, *, location: str | None = None) -> ExtensionError:
    """Build a ``bundle-discovery-malformed`` error payload."""
    return ExtensionError(
        code="bundle-discovery-malformed",
        message=message,
        location=location,
        content=content,
        hint=_MALFORMED_HINT,
    )


def _malformed_sentinel(content: str, message: str) -> LoadResult:
    """A warning-only :class:`LoadResult` for an unresolvable ``lfx.bundles`` declaration.

    Carries the diagnostic on ``warnings`` (not ``errors``) so ``ok`` stays
    ``True`` and the malformed declaration never flips a startup gate.
    """
    sentinel = LoadResult(slot=None, source_path=None, distribution=None)
    sentinel.warnings.append(_malformed_error(content, message))
    return sentinel

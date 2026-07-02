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
Every discovery failure degrades to a typed *warning* (never an error that
aborts server startup), with one code per failure mode so the rendered
message and hint fit the actual mistake:

- ``bundle-discovery-malformed`` -- the entry-point declaration does not
  resolve to an importable package directory (including a parent package
  whose ``__init__`` raises during ``find_spec``); fix the declaration.
- ``bundles-provider-name-invalid`` -- a provider folder is not a valid
  bundle name (e.g. not lowercased); rename the directory.
- ``bundles-root-unreadable`` -- a resolved root cannot be enumerated;
  check permissions.
- ``duplicate-lfx-bundles-provider`` -- the same provider name appears in
  more than one root; the first discovered root wins.
- ``path-escape`` -- a provider directory (e.g. a symlink) resolves outside
  the bundle root; the trust boundary is the installed package tree.
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
    result carries the same typed ``bundle-shadowed`` error the cross-source
    resolver emits for every other shadow pair.  Skipping the
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

    A namespace package split across several sys.path entries yields one root
    per portion -- every portion may carry providers.  Resolved roots are
    deduplicated by resolved path so two declarations naming the same package
    (or overlapping portions) never walk a directory twice, which would make
    every provider in it self-shadow.
    """
    if entry_points is None:
        from importlib import metadata as importlib_metadata

        entry_points = importlib_metadata.entry_points(group=LFX_BUNDLES_ENTRY_POINT_GROUP)

    roots: list[_BundleRoot] = []
    sentinels: list[LoadResult] = []
    seen_root_paths: set[Path] = set()
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
        # ``find_spec`` does not import the target module itself, but for a
        # dotted declaration like ``pkg.bundles`` it DOES import the parent
        # ``pkg`` -- arbitrary third-party ``__init__`` code that can raise
        # anything, not just ImportError.  Catch broadly and degrade to the
        # malformed sentinel: an escape here would propagate to the palette
        # cache's catch-all, which replaces the WHOLE extension_components
        # mapping with {} -- one rotten declaration must not wipe every
        # installed/seed/dev/inline bundle for the boot.
        try:
            spec = importlib.util.find_spec(module_name)
        except Exception as exc:  # noqa: BLE001 -- third-party __init__ can raise anything
            sentinels.append(
                _malformed_sentinel(label, f"find_spec({module_name!r}) failed: {type(exc).__name__}: {exc}")
            )
            continue
        package_dirs = [d for d in _spec_package_dirs(spec) if d.is_dir()]
        if not package_dirs:
            sentinels.append(
                _malformed_sentinel(label, f"module {module_name!r} does not resolve to a package directory.")
            )
            continue
        extension_id, extension_version = _distribution_identity(ep, fallback_id=module_name)
        for package_dir in package_dirs:
            resolved = package_dir.resolve()
            if resolved in seen_root_paths:
                continue
            seen_root_paths.add(resolved)
            roots.append(_BundleRoot(path=package_dir, extension_id=extension_id, extension_version=extension_version))
    return roots, sentinels


def _load_bundle_roots(
    roots: Iterable[_BundleRoot],
    *,
    claimed_bundles: Mapping[str, tuple[str, str]] | None = None,
) -> list[LoadResult]:
    """Folder-walk each resolved root, loading every valid subdirectory at @official.

    First-wins on duplicate bundle names across roots (the loser emits a typed
    ``duplicate-lfx-bundles-provider`` warning); names in ``claimed_bundles``
    (already won by a higher-precedence installed/seed source) are skipped
    *without importing* -- carrying the same ``bundle-shadowed`` error the
    cross-source resolver emits -- so the winner's
    ``_lfx_ext.official.<bundle>.*`` sys.modules entries are never
    overwritten.  Subdirectories whose name is not a valid bundle name emit
    ``bundles-provider-name-invalid``; a root that cannot be enumerated emits
    ``bundles-root-unreadable``.  Internal directories (dot-prefixed,
    underscore-prefixed, or in :data:`SKIP_DIR_NAMES`) are skipped silently --
    they are package machinery, not providers.
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
                ExtensionError(
                    code="bundles-root-unreadable",
                    message=f"{type(exc).__name__}: {exc}",
                    location=str(root.path),
                    content=str(root.path),
                    hint="Check the directory's permissions; this root is skipped for this boot.",
                )
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
                    ExtensionError(
                        code="path-escape",
                        message=(f"provider directory {name!r} resolves outside the bundle root {root.path}; skipped."),
                        location=str(child),
                        content=name,
                        hint=(
                            "Replace the symlink with a real directory inside the bundle root; "
                            "the trust boundary is the installed package tree."
                        ),
                    )
                )
                results.append(result)
                continue

            result = LoadResult(slot=SLOT_OFFICIAL, source_path=child, manifestless=True)

            if not BUNDLE_NAME_RE.match(name):
                result.warnings.append(
                    ExtensionError(
                        code="bundles-provider-name-invalid",
                        message=(
                            f"provider directory {name!r} (under {root.path}) is not a valid bundle "
                            "name; lowercase snake_case (a-z, 0-9, _), 2-64 characters."
                        ),
                        location=str(child),
                        content=name,
                        hint="Rename the provider directory to a valid bundle name.",
                    )
                )
                results.append(result)
                continue

            if name in claimed:
                # Cross-source shadow: same code AND same severity (errors)
                # as _resolve_bundle_shadowing emits for every other shadow
                # pair, so filtering by code never mixes semantics.
                winner_kind, winner_path = claimed[name]
                result.bundle = name
                result.errors.append(
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
                # Same-tier duplicate (two lfx.bundles roots ship the same
                # provider): a dedicated code, NOT ``bundle-shadowed`` --
                # that one means cross-source precedence and its rendered
                # template would mislead here.  Mirrors the inline tier's
                # ``duplicate-inline-bundle``.
                result.bundle = name
                result.warnings.append(
                    ExtensionError(
                        code="duplicate-lfx-bundles-provider",
                        message=(
                            f"Manifest-less bundle {name!r} already discovered from {seen_names[name]}; "
                            f"skipping the copy at {child}."
                        ),
                        location=str(child),
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


def _spec_package_dirs(spec: importlib.machinery.ModuleSpec | None) -> list[Path]:
    """Return every on-disk directory a package spec points at.

    Only package specs qualify (``submodule_search_locations`` is set for both
    regular and namespace packages).  A namespace package split across several
    sys.path entries carries one location per portion, and every portion may
    hold providers, so all of them are returned.  A plain-module spec returns
    ``[]`` -- a single-file module has no provider subdirectories, and falling
    back to the module file's parent would folder-walk unrelated sibling
    directories (in a real install: all of site-packages) as bundles.
    """
    if spec is None:
        return []
    return [Path(location) for location in (spec.submodule_search_locations or [])]


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


def _malformed_error(content: str, message: str) -> ExtensionError:
    """Build a ``bundle-discovery-malformed`` error payload.

    Reserved for *declaration*-level failures (an entry point that does not
    resolve to an importable package directory) -- its hint tells the operator
    to fix the entry-point declaration.  Provider-name and root-enumeration
    failures carry their own codes (``bundles-provider-name-invalid``,
    ``bundles-root-unreadable``) whose hints fit those mistakes.
    """
    return ExtensionError(
        code="bundle-discovery-malformed",
        message=message,
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

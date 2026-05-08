"""Manifest-first precedence over ``langflow.plugins`` entry-points.

This is the bridge between the new manifest-based loader and the legacy
``langflow.plugins`` entry-point system that third parties already use to
register components.  The rule is simple: if a distribution ships an
extension manifest, the manifest is the source of truth for its
components; its ``langflow.plugins`` *component* entry-points are skipped
to avoid double registration.  Non-component entry-points (services,
routes) on the same distribution are unaffected -- the caller's loop is
responsible for that distinction.

The installed-package / seed-dir discovery flow consumes the same
primitives at server startup to drive the read-only @official slot.  The
helpers live in their own module so that downstream consumer gets a stable
import surface to reach for.
"""

from __future__ import annotations

import logging
import re
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import TYPE_CHECKING

from lfx.extension.loader._detection import is_component_subclass

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Distribution-name normalization (PEP 503)
# ---------------------------------------------------------------------------

_PEP503_NORMALIZE_RE = re.compile(r"[-_.]+")


def canonicalize_distribution(name: str) -> str:
    """Canonicalize a distribution name per PEP 503 (lowercase + collapse [-_.])."""
    return _PEP503_NORMALIZE_RE.sub("-", name).lower()


# ---------------------------------------------------------------------------
# Distribution introspection
# ---------------------------------------------------------------------------


def _distribution_manifest_path(dist: importlib_metadata.Distribution) -> Path | None:
    """Locate an extension manifest shipped by ``dist``, if any.

    Both v0 manifest forms are supported:

        1. A wheel that ships ``extension.json`` as package data (preferred
           because it carries ``$schema`` for editor support).
        2. A distribution that ships ``pyproject.toml`` with a
           ``[tool.langflow.extension]`` section.

    ``extension.json`` wins on collision so an Extension that ships both
    is treated as a single Extension whose canonical manifest is the JSON
    file, matching :func:`lfx.extension.manifest.load_manifest`'s discovery
    order.

    For the pyproject form, the file is only accepted as a manifest if its
    ``[tool.langflow.extension]`` section is actually present and parses;
    a stray ``pyproject.toml`` shipped by an unrelated distribution is
    ignored.

    Returns the absolute path to the manifest file, or ``None``.
    """
    files = dist.files
    if files is None:
        return None

    pyproject_candidate: Path | None = None
    for relative in files:
        if not relative.parts:
            continue
        last = relative.parts[-1]
        if last == "extension.json":
            try:
                located = Path(dist.locate_file(relative))
            except (OSError, ValueError):
                # ``locate_file`` may raise on unusual setups (e.g. namespace
                # packages without a concrete root); treat as "not found"
                # without breaking the rest of the scan.
                continue
            if located.is_file():
                # extension.json wins outright -- skip any pyproject seen later.
                return located
        elif last == "pyproject.toml" and pyproject_candidate is None:
            try:
                located = Path(dist.locate_file(relative))
            except (OSError, ValueError):
                continue
            if located.is_file():
                pyproject_candidate = located

    if pyproject_candidate is not None and _pyproject_has_extension_section(pyproject_candidate):
        return pyproject_candidate
    return None


def _pyproject_has_extension_section(pyproject_path: Path) -> bool:
    """Return True iff ``pyproject_path`` declares ``[tool.langflow.extension]``.

    Detects section *presence* only -- intentionally does NOT run schema
    validation. A pyproject whose ``[tool.langflow.extension]`` section
    exists but has missing/invalid required fields still returns True so
    the caller registers it as a manifest-shipping distribution; the
    typed ``manifest-invalid`` error is then surfaced by
    :func:`load_extension`'s normal failure path. Conflating "section
    absent" with "section malformed" would silently drop pyproject-form
    Extensions whose authors typo'd a field.

    Behavior matrix:
        - Section absent or pyproject TOML unparseable -> False (treat as
          a regular non-manifest package).
        - Section present and is a table (valid or schema-invalid) -> True.
        - Section present but is not a table (e.g. list) -> True; the
          author clearly intended to declare an extension and the
          downstream loader should report it.
    """
    # Imported here rather than at module level to avoid a potential cycle:
    # manifest.py -> errors.py -> extension/__init__.py -> loader/__init__.py
    # would otherwise route back through this module during package init.
    from lfx.extension.manifest import _read_pyproject_extension

    try:
        section = _read_pyproject_extension(pyproject_path)
    except ValueError:
        # Unparseable TOML: not specifically a langflow extension issue,
        # let the rest of the system treat it as a regular package.
        return False
    except TypeError:
        # [tool.langflow.extension] exists but isn't a table. The author
        # intended to declare an extension; let load_extension produce
        # the typed manifest-invalid error rather than silently drop.
        return True
    except OSError:
        return False
    return section is not None


def _distribution_canonical_name(dist: importlib_metadata.Distribution) -> str | None:
    """Return the PEP-503-canonical name of a distribution, or ``None``.

    Defensive: a non-string ``Name`` (e.g. a MagicMock in tests, or an
    unusual metadata backend) returns ``None`` so the canonical-name
    machinery doesn't crash an entry-point partition pass.
    """
    try:
        raw = dist.metadata["Name"]
    except (KeyError, AttributeError, TypeError):
        return None
    if not isinstance(raw, str) or not raw:
        return None
    return canonicalize_distribution(raw)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def installed_extension_roots(
    distributions: Iterable[importlib_metadata.Distribution] | None = None,
) -> dict[str, Path]:
    """Map canonical distribution name -> extension root for installed manifests.

    Used by the entry-point bridge to skip ``langflow.plugins`` registrations
    for distributions that ship a manifest (manifest-first precedence).
    The full discovery + warning surface used at server startup is
    :func:`discover_installed_extensions` -- this primitive only returns the
    resolved mapping, never warnings.

    Args:
        distributions: Override the distribution iterator (test seam).
            Defaults to ``importlib.metadata.distributions()``.

    Returns:
        Dict keyed by canonical distribution name; the value is the
        directory containing ``extension.json``.  When two distributions
        share a canonical name (broken venv), the lexicographically-first
        manifest path wins for determinism.
    """
    return {name: root for name, (root, _) in _resolve_distribution_roots(distributions).items()}


def _resolve_distribution_roots(
    distributions: Iterable[importlib_metadata.Distribution] | None,
) -> dict[str, tuple[Path, list[Path]]]:
    """Inner helper: resolve roots and collect duplicate manifest paths.

    Returns a dict keyed by canonical name, value is
    ``(winning_root, list_of_all_manifest_paths)``.  When the list has more
    than one entry, the canonical name was claimed by multiple distributions
    and the caller may surface ``duplicate-distribution`` warnings.
    """
    if distributions is None:
        distributions = importlib_metadata.distributions()

    intermediate: dict[str, list[Path]] = {}
    for dist in distributions:
        manifest_path = _distribution_manifest_path(dist)
        if manifest_path is None:
            continue
        canonical = _distribution_canonical_name(dist)
        if canonical is None:
            continue
        intermediate.setdefault(canonical, []).append(manifest_path)

    resolved: dict[str, tuple[Path, list[Path]]] = {}
    for canonical, manifests in intermediate.items():
        sorted_manifests = sorted(manifests, key=str)
        winner = sorted_manifests[0].parent
        resolved[canonical] = (winner, sorted_manifests)
    return resolved


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


def _entry_point_loads_to_component(ep: importlib_metadata.EntryPoint) -> bool:
    """Try to load ``ep`` and decide whether the loaded value is a Component.

    Defensive: any load-time failure returns False so the entry-point is
    treated as non-component (kept) by the caller. Surfacing the failure
    as a typed error belongs to the layer that actually wants to load the
    component (LE-1015 loader proper); this helper exists only to drive
    manifest-first precedence for runtime entry-point consumers.
    """
    try:
        value = ep.load()
    except BaseException as exc:  # noqa: BLE001
        # Same trade-off as the bundle loader: at startup we never want
        # one bad entry-point to abort the whole filter pass.
        logger.debug("Could not load entry-point %r for component check: %s", ep.name, exc)
        return False
    return is_component_subclass(value)


def filter_component_entry_points(
    entry_points: Iterable[importlib_metadata.EntryPoint],
    *,
    skip: Iterable[str] | None = None,
    is_component: Callable[[importlib_metadata.EntryPoint], bool] | None = None,
) -> tuple[list[importlib_metadata.EntryPoint], list[importlib_metadata.EntryPoint]]:
    """Type-aware partition: skip COMPONENT entry-points on manifest-shipping dists.

    Where :func:`filter_plugin_entry_points` partitions by distribution name
    only, this function additionally inspects each entry-point's loaded
    value: only those that load to a Component subclass are eligible for
    skipping. This is the function runtime callers (``plugin_routes`` etc.)
    should use so that non-component entry-points (routes, services, hooks)
    on a manifest-shipping distribution still load through the legacy path,
    per the AC's "non-component entry-points are unaffected" promise.

    Args:
        entry_points: Entry points from ``importlib.metadata.entry_points``.
        skip: Canonical distribution names whose component entry-points
            should be skipped. Defaults to
            :func:`manifest_owning_distributions`.
        is_component: Predicate that loads + inspects an EP. Defaults to
            :func:`_entry_point_loads_to_component`. Test seam.

    Returns:
        ``(kept, skipped)``. Stable ordering preserved within each list.
    """
    skip_set = frozenset(skip) if skip is not None else manifest_owning_distributions()
    is_component_fn = is_component if is_component is not None else _entry_point_loads_to_component

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
        if canonical in skip_set and is_component_fn(ep):
            skipped.append(ep)
        else:
            kept.append(ep)
    return kept, skipped

"""Manifest-first precedence over ``langflow.plugins`` entry-points (LE-1015).

This is the bridge between the new manifest-based loader and the legacy
``langflow.plugins`` entry-point system that third parties already use to
register components.  The rule is simple: if a distribution ships an
extension manifest, the manifest is the source of truth for its
components; its ``langflow.plugins`` *component* entry-points are skipped
to avoid double registration.  Non-component entry-points (services,
routes) on the same distribution are unaffected -- the caller's loop is
responsible for that distinction.

LE-1022 will use the same primitives at server startup to drive the
read-only @official slot (installed-package + seed-dir discovery).  The
helpers live in their own module so that downstream module gets a stable
import surface to reach for.
"""

from __future__ import annotations

import re
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable


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
    return canonicalize_distribution(raw)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


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

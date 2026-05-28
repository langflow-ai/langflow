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

import importlib.util
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
    """Return the manifest path shipped by ``dist`` (extension.json or pyproject.toml), or None.

    extension.json wins on collision; pyproject.toml is accepted only when
    it declares ``[tool.langflow.extension]``.

    Editable installs (``pip install -e``, ``uv pip install --editable``)
    typically expose only dist-info files via ``dist.files`` -- the source
    tree lives outside the site-packages and is reached at import time via
    a ``.pth`` shim.  When the dist-info pass finds no manifest, fall back
    to ``direct_url.json`` (PEP 610) to locate the editable project root
    and look for ``extension.json`` / ``pyproject.toml`` there.  Without
    this fallback, ``lfx-duckduckgo`` and friends installed via ``uv sync``
    workspace links never reach :func:`load_installed_extensions`.
    """
    files = dist.files
    pyproject_candidate: Path | None = None
    if files is not None:
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

    # Fallback: editable install.  PEP 610 ``direct_url.json`` records the
    # source URL; for editable installs the URL is a ``file://`` path to the
    # project root, which is where the manifest lives.
    return _editable_manifest_path(dist)


def _editable_manifest_path(dist: importlib_metadata.Distribution) -> Path | None:
    """Resolve the manifest of an editable install whose ``dist.files`` is dist-info-only.

    Tries two fallbacks in order:

    1. The ``langflow.extensions`` entry-point group.  When a bundle
       declares ``[project.entry-points."langflow.extensions"] foo = "lfx_foo"``
       the entry-point's value is the dotted package path that ships
       ``extension.json``; importing that package gives us the source
       directory regardless of how the dist was installed.

    2. PEP 610 ``direct_url.json`` for ``editable=true`` distributions.
       The recorded URL points at the project root; we look for
       ``extension.json`` (or a ``[tool.langflow.extension]`` pyproject)
       directly there.

    Returns ``None`` if neither path yields a manifest.  Both paths are
    necessary because (a) installed wheels list the package's
    ``extension.json`` in ``dist.files`` so they don't reach this fallback,
    and (b) editable installs that use ``langflow.extensions`` entry-points
    point at the package, while editable installs that don't may still
    have a top-level manifest.
    """
    manifest = _manifest_via_entry_point(dist)
    if manifest is not None:
        return manifest
    return _manifest_via_direct_url(dist)


def _manifest_via_entry_point(dist: importlib_metadata.Distribution) -> Path | None:
    """Find a manifest via this distribution's ``langflow.extensions`` entry-point.

    Locates the package directory via ``importlib.util.find_spec`` rather
    than importing the package, so a manifest-discovery pass at startup
    does not trigger arbitrary side-effects from a bundle's ``__init__``.
    """
    import importlib.util

    try:
        eps = dist.entry_points
    except (OSError, AttributeError, TypeError):
        return None
    if eps is None:
        return None

    candidate_modules: list[str] = []
    for ep in eps:
        if getattr(ep, "group", None) == "langflow.extensions":
            value = (getattr(ep, "value", "") or "").split(":", 1)[0].strip()
            if value:
                candidate_modules.append(value)

    for module_name in candidate_modules:
        try:
            spec = importlib.util.find_spec(module_name)
        except (ImportError, ValueError, ModuleNotFoundError):
            continue
        if spec is None or spec.origin is None:
            continue
        package_dir = Path(spec.origin).parent
        manifest = package_dir / "extension.json"
        if manifest.is_file():
            return manifest
    return None


def _manifest_via_direct_url(dist: importlib_metadata.Distribution) -> Path | None:
    """Resolve the manifest from PEP 610 ``direct_url.json`` for editable installs."""
    import json
    from urllib.parse import urlparse

    try:
        raw = dist.read_text("direct_url.json")
    except (OSError, FileNotFoundError, AttributeError):
        # ``AttributeError`` covers test doubles that don't implement the
        # full ``Distribution`` interface; ``OSError`` covers the production
        # case where the file is missing or unreadable.
        return None
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None
    dir_info = payload.get("dir_info") or {}
    if not isinstance(dir_info, dict) or not dir_info.get("editable"):
        return None

    url = payload.get("url")
    if not isinstance(url, str):
        return None
    parsed = urlparse(url)
    if parsed.scheme != "file":
        return None
    project_root = Path(parsed.path)
    if not project_root.is_dir():
        return None

    manifest = project_root / "extension.json"
    if manifest.is_file():
        return manifest

    pyproject = project_root / "pyproject.toml"
    if pyproject.is_file() and _pyproject_has_extension_section(pyproject):
        return pyproject
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

    Args:
        distributions: Override the distribution iterator (test seam).
            Defaults to ``importlib.metadata.distributions()``.

    Returns:
        Dict keyed by canonical distribution name; the value is the
        directory containing the manifest. When two distributions share a
        canonical name (broken venv), the lexicographically-first manifest
        path wins for determinism; :func:`load_installed_extensions` emits
        the typed ``duplicate-distribution`` error in that case.
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
    """Return the canonical distribution names that ship an extension manifest.

    Two distributions sharing a canonical name (broken venv) collapse to a
    single entry in the returned set; the typed ``duplicate-distribution``
    error is emitted by :func:`load_installed_extensions`, not this
    primitive. Callers that consume this set in isolation (e.g. directly
    feeding ``filter_component_entry_points``) get the conservative
    behavior -- both distributions' component entry-points are skipped --
    but should also call ``load_installed_extensions`` to surface the
    diagnostic to operators.
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
    """Try to decide whether ``ep`` resolves to a Component subclass.

    Lazy: tries ``importlib.util.find_spec`` first so a filter-time check
    does NOT execute arbitrary third-party module-level code as a side
    effect.  Only falls through to ``ep.load()`` if the spec lookup
    cannot disambiguate (e.g. the entry-point points at a class inside
    a module rather than at the module itself).

    The sibling helper ``_manifest_via_entry_point`` (above) is explicit
    that manifest discovery must not trigger module-level side effects;
    this predicate now matches that posture for the runtime filter.

    Any load-time failure returns False so the entry-point is treated as
    non-component (kept) by the caller.  The narrow ``Exception`` (no
    longer ``BaseException``) intentionally lets ``SystemExit`` and
    ``KeyboardInterrupt`` propagate so a CTRL-C during startup is not
    silently swallowed by the filter pass.
    """
    # Fast path: most component entry-points point at a module-level
    # symbol (``my_pkg.components.thing:ThingComponent``).  importlib's
    # find_spec can locate the module without executing it, so we can
    # skip the eager load in the common case.  The name component of the
    # entry-point's value (the bit after the colon, if present) is what
    # tells us whether the symbol is a class -- but find_spec only gives
    # us module presence, not contents, so we still need ep.load() to
    # confirm a class.  The win here is that for entry-points whose
    # module clearly does NOT exist (broken install, missing dependency)
    # we short-circuit to False before importing anything.
    try:
        module_name, _, _ = ep.value.partition(":")
        if module_name and importlib.util.find_spec(module_name) is None:
            return False
    except (ValueError, ImportError, AttributeError):
        # Malformed ep.value or import-time error during find_spec.  Fall
        # through to the eager load below so the existing behaviour is
        # preserved for unusual entry-point shapes.
        pass

    try:
        value = ep.load()
    except Exception as exc:  # noqa: BLE001
        # Same trade-off as the bundle loader, but narrower: at startup
        # we never want one bad entry-point to abort the whole filter
        # pass, but we do not swallow SystemExit/KeyboardInterrupt.
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

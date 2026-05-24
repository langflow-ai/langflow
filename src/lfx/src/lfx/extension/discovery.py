"""Production-install discovery for the Langflow Extension System.

This module owns the two production install sources for Modes A, B, and C:

    1. **Installed Python distributions** -- the primary path. ``pip install
       langflow lfx-<provider>`` puts a manifest-shipping distribution on
       ``importlib.metadata.distributions()``; we walk that iterator at
       server startup and surface every distribution that ships an
       ``extension.json`` or a ``[tool.langflow.extension]`` section in its
       ``pyproject.toml``.

    2. **Seed directories** -- an optional filesystem source for Docker
       images or k8s deployments that prefer an explicit on-disk layout.
       Defaults to ``/opt/langflow/bundles/`` when present; the
       ``LANGFLOW_SEED_DIR`` environment variable overrides this with one
       or more paths joined by ``os.pathsep``.

Both sources produce :class:`DiscoveredExtension` records.  Discovery is
read-only: it never imports bundle code, never mutates the filesystem, and
never touches the registry.  The :mod:`lfx.extension.registry` service is
what actually pins these into the runtime; ``register_installed`` and
``register_seed`` consume the same :class:`DiscoveredExtension` shape.

This is the production install path, not the loading path.  Component
loading is downstream of this; the Extension records here are
what the loader ultimately resolves to a concrete Bundle directory.

Errors are surfaced as :class:`~lfx.extension.errors.ExtensionError`
instances paired with their discovery context.  A malformed manifest does
not abort the scan -- the producer collects the error, skips the
distribution, and keeps walking so a single broken package can't hide its
neighbours.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from lfx.extension._paths import SKIP_DIR_NAMES, is_within
from lfx.extension.errors import ExtensionError
from lfx.extension.manifest import (
    BundleRef,
    ExtensionManifest,
    ManifestSource,
    _read_extension_json,
    _read_pyproject_extension,
    load_manifest,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_SEED_DIR: Path = Path("/opt/langflow/bundles")
"""Default filesystem seed directory used when ``LANGFLOW_SEED_DIR`` is unset.

Chosen to match the path operators bake into Mode B/C Docker images.
Outside Docker the directory typically does not exist, in which case
discovery silently skips it -- the absence is normal, not an error."""

SEED_DIR_ENV_VAR: str = "LANGFLOW_SEED_DIR"
"""Environment variable that overrides :data:`DEFAULT_SEED_DIR`.  Accepts a
single directory or several joined by ``os.pathsep`` (``:`` on POSIX,
``;`` on Windows), mirroring ``LANGFLOW_COMPONENTS_PATH``."""

SourceKind = Literal["installed", "seed"]


# ---------------------------------------------------------------------------
# DiscoveredExtension
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DiscoveredExtension:
    """A manifest-shipping bundle source surfaced by startup discovery.

    Frozen so callers can place these into sets / dicts and forward them to
    the events pipeline without worrying about mutation.

    Attributes:
        extension_id: The :attr:`ExtensionManifest.id` value.
        version: The :attr:`ExtensionManifest.version` value.
        bundle_name: The single bundle's name (v0 ships exactly one).
        manifest: The parsed manifest source (path + kind preserved).
        source_kind: Where the manifest came from -- ``installed`` for an
            ``importlib.metadata`` distribution, ``seed`` for a filesystem
            subdirectory.
        source: A short, human-readable origin label.  PEP-503-canonical
            distribution name for ``installed``; absolute path of the seed
            subdirectory for ``seed``.
        extension_root: Directory that contains the manifest file.  This is
            the path the loader hands to ``validate_extension`` /
            ``load_extension`` once those subsystems land.
    """

    extension_id: str
    version: str
    bundle_name: str
    manifest: ManifestSource
    source_kind: SourceKind
    source: str
    extension_root: Path

    @property
    def slot(self) -> Literal["official"]:
        """Read-only Extensions registered by discovery always live at @official.

        Property rather than a stored field so the invariant (slot ==
        ``official`` for every discovery record in this milestone) cannot
        drift.  The @extra slot is reserved for loose
        ``LANGFLOW_COMPONENTS_PATH`` folders; nothing in this module
        produces it.
        """
        return "official"


# ---------------------------------------------------------------------------
# Distribution-name normalization (PEP 503)
# ---------------------------------------------------------------------------

_PEP503_NORMALIZE_RE: re.Pattern[str] = re.compile(r"[-_.]+")


def canonicalize_distribution(name: str) -> str:
    """Canonicalize a distribution name per PEP 503 (lowercase, collapse [-_.])."""
    return _PEP503_NORMALIZE_RE.sub("-", name).lower()


# ---------------------------------------------------------------------------
# Bundle path-safety verification
# ---------------------------------------------------------------------------


def _verify_bundle_path_safety(
    extension_root: Path,
    bundle: BundleRef,
) -> ExtensionError | None:
    """Confirm ``bundle.path`` (when resolved under ``extension_root``) stays inside.

    Discovery records flow into the loader, which imports code from
    ``bundle.path``.  The schema-level validator on :class:`BundleRef`
    rejects ``..`` and absolute paths syntactically, but a symlink swap
    or a path that resolves outside the extension root must be caught
    here so the production-install path enforces the same trust boundary
    as ``validate_extension``.

    Returns ``None`` on success, or a typed ``path-escape`` error.
    """
    candidate = extension_root / bundle.path
    try:
        resolved = candidate.resolve(strict=False)
    except OSError as exc:
        return ExtensionError(
            code="path-escape",
            message=f"Could not resolve bundle path: {exc}",
            location=bundle.path,
            content=bundle.path,
            hint="Make sure the bundle path resolves to a directory under the manifest.",
        )
    if not is_within(resolved, extension_root):
        root_resolved = extension_root.resolve(strict=False)
        return ExtensionError(
            code="path-escape",
            message=(
                f"Bundle path {bundle.path!r} resolves to {resolved}, which is "
                f"outside the extension root {root_resolved}."
            ),
            location=bundle.path,
            content=bundle.path,
            hint="Move the bundle directory inside the extension root or remove the symlink.",
        )
    return None


# ---------------------------------------------------------------------------
# Installed-distribution discovery
# ---------------------------------------------------------------------------


def _distribution_canonical_name(dist: importlib_metadata.Distribution) -> str | None:
    """Return the canonical PEP-503 name of *dist*, or ``None`` if absent.

    Defensive: a distribution metadata backend that returns a non-string
    ``Name`` (or no ``Name`` at all) yields ``None`` so a single malformed
    package can't crash the whole scan.
    """
    try:
        raw = dist.metadata["Name"]
    except (KeyError, AttributeError, TypeError):
        return None
    if not isinstance(raw, str) or not raw:
        return None
    return canonicalize_distribution(raw)


def _distribution_manifest_path(dist: importlib_metadata.Distribution) -> Path | None:
    """Locate the manifest file shipped by *dist*, or ``None``.

    Acceptance order matches :func:`load_manifest`: ``extension.json`` wins
    if present; otherwise we fall back to a ``pyproject.toml`` that
    declares a ``[tool.langflow.extension]`` table.

    For editable installs whose ``dist.files`` only surfaces ``dist-info/``
    entries (the ``pip install -e`` / ``uv pip install -e`` case), we fall
    back to the ``langflow.extensions`` entry-point group declared in the
    distribution's ``pyproject.toml``.

    A missing or unreadable file iteration is treated as "no manifest"
    rather than as an error: the caller's scan should keep walking.
    """
    files = dist.files
    if files is not None:
        pyproject_candidate: Path | None = None
        for relative in files:
            if not relative.parts:
                continue
            last = relative.parts[-1]
            if last == "extension.json":
                try:
                    located = Path(dist.locate_file(relative))
                except (OSError, ValueError):
                    continue
                if located.is_file():
                    return located
            elif last == "pyproject.toml" and pyproject_candidate is None:
                try:
                    located = Path(dist.locate_file(relative))
                except (OSError, ValueError):
                    continue
                if located.is_file():
                    pyproject_candidate = located

        if pyproject_candidate is not None:
            try:
                if _pyproject_declares_extension(pyproject_candidate):
                    return pyproject_candidate
            except OSError:
                # Unreadable pyproject that might declare an extension.  Surface
                # the candidate path so the downstream manifest-unreadable check
                # fires with an actionable error instead of silently dropping
                # the distribution.
                return pyproject_candidate

    return _distribution_manifest_path_via_entry_points(dist)


def _distribution_manifest_path_via_entry_points(
    dist: importlib_metadata.Distribution,
) -> Path | None:
    """Resolve the manifest of an editable install via its entry-point.

    Editable installs (``pip install -e``, ``uv pip install -e``) record only
    ``dist-info/`` entries in ``dist.files``: the package's source tree lives
    behind a ``.pth`` file rather than under a wheel-installed directory, so
    the ``files`` scan above never sees ``extension.json``.  The
    ``langflow.extensions`` entry-point points at the package that ships the
    manifest; we resolve it via :func:`importlib.util.find_spec` (which runs
    the import-system finders but **never executes the module's body**) and
    look for the manifest in the resulting package directory.

    Returns ``None`` when the distribution has no usable entry-point, the
    referenced module cannot be located on ``sys.path``, or the located
    directory does not contain a manifest.
    """
    import importlib.util

    try:
        eps = dist.entry_points
    except (OSError, AttributeError, TypeError):
        return None
    if eps is None:
        return None

    try:
        selected = list(eps.select(group="langflow.extensions"))
    except AttributeError:
        # Older importlib.metadata returns a plain tuple of EntryPoint with
        # no .select() helper; filter manually.
        selected = [ep for ep in eps if getattr(ep, "group", None) == "langflow.extensions"]

    for ep in selected:
        module_name = (getattr(ep, "value", "") or "").split(":", 1)[0].strip()
        if not module_name:
            continue
        try:
            spec = importlib.util.find_spec(module_name)
        except (ImportError, ValueError, ModuleNotFoundError):
            continue
        if spec is None:
            continue

        candidate_dirs: list[Path] = []
        if spec.submodule_search_locations:
            candidate_dirs.extend(Path(loc) for loc in spec.submodule_search_locations)
        elif spec.origin and spec.origin not in {"built-in", "frozen"}:
            candidate_dirs.append(Path(spec.origin).parent)

        for package_dir in candidate_dirs:
            extension_json = package_dir / "extension.json"
            if extension_json.is_file():
                return extension_json
            pyproject = package_dir / "pyproject.toml"
            if pyproject.is_file():
                try:
                    if _pyproject_declares_extension(pyproject):
                        return pyproject
                except OSError:
                    return pyproject
    return None


def _pyproject_declares_extension(pyproject_path: Path) -> bool:
    """Return ``True`` iff *pyproject_path* contains ``[tool.langflow.extension]``.

    Detects section *presence* only; intentionally does NOT validate the
    schema.  A pyproject whose section exists but is malformed must still
    be visible to discovery so the caller can emit a typed
    ``manifest-invalid`` error rather than silently dropping the package.

    An OSError on read (permission denied, etc.) propagates so the caller
    can distinguish "section absent" (skip) from "could not read file"
    (surface as a typed error and reach the manifest-unreadable path).
    """
    try:
        section = _read_pyproject_extension(pyproject_path)
    except ValueError:
        # Unparseable TOML: not specifically a Langflow concern, treat as
        # "not a manifest-shipping package" and keep scanning.
        return False
    except TypeError:
        # [tool.langflow.extension] exists but isn't a table.  The author
        # clearly intended to declare an extension, so surface the package
        # to discovery; the typed manifest-invalid will fire downstream.
        return True
    # Note: OSError propagates intentionally. A permission/I/O error on a
    # pyproject.toml that *might* declare an extension is not the same as
    # "no extension here" -- swallowing it would silently drop a legitimate
    # install. Callers gate on this via the surrounding logic in
    # _distribution_manifest_path / _build_seed_record.
    return section is not None


def _build_installed_record(
    dist: importlib_metadata.Distribution,
    manifest_path: Path,
) -> tuple[DiscoveredExtension | None, ExtensionError | None]:
    """Parse the manifest at *manifest_path* into a :class:`DiscoveredExtension`.

    Returns ``(record, None)`` on success or ``(None, error)`` on failure.
    """
    canonical = _distribution_canonical_name(dist) or manifest_path.parent.name
    extension_root = manifest_path.parent

    try:
        if manifest_path.name == "extension.json":
            data = _read_extension_json(manifest_path)
            kind = "extension.json"
        else:
            section = _read_pyproject_extension(manifest_path)
            if section is None:
                # Defensive: the pre-filter said this pyproject declared
                # the section.  If a concurrent edit removed it between
                # discovery passes, treat as no manifest.
                return None, None
            data = section
            kind = "pyproject.toml"
    except (ValueError, TypeError, OSError) as exc:
        return None, ExtensionError(
            code="manifest-unreadable",
            message=str(exc),
            location=str(manifest_path),
            content=canonical,
            hint="Make sure the file exists, is UTF-8, and is well-formed JSON or TOML.",
        )

    try:
        manifest = ExtensionManifest.model_validate(data)
    except Exception as exc:  # noqa: BLE001 - pydantic raises ValidationError; bare Exception keeps the scan robust
        return None, ExtensionError(
            code="manifest-invalid",
            message=str(exc),
            location=str(manifest_path),
            content=canonical,
            hint="Run `lfx extension validate` against the package source to see the per-field detail.",
        )

    bundle = manifest.bundles[0]
    path_error = _verify_bundle_path_safety(extension_root, bundle)
    if path_error is not None:
        return None, path_error
    source = ManifestSource(manifest=manifest, path=manifest_path, kind=kind)
    return (
        DiscoveredExtension(
            extension_id=manifest.id,
            version=manifest.version,
            bundle_name=bundle.name,
            manifest=source,
            source_kind="installed",
            source=canonical,
            extension_root=extension_root,
        ),
        None,
    )


def discover_installed_extensions(
    distributions: Iterable[importlib_metadata.Distribution] | None = None,
) -> tuple[list[DiscoveredExtension], list[ExtensionError]]:
    """Scan installed distributions for manifest-shipping packages.

    Args:
        distributions: Override the distribution iterator (test seam).
            Defaults to ``importlib.metadata.distributions()``.

    Returns:
        ``(extensions, errors)``. ``extensions`` is the list of valid
        :class:`DiscoveredExtension` records in the order distributions
        were yielded. ``errors`` carries one
        :class:`~lfx.extension.errors.ExtensionError` per package whose
        manifest existed but failed to parse / validate; packages without a
        manifest are silently skipped (they're regular Python libraries).

    A duplicate canonical distribution name (the broken-venv case where
    two ``site-packages`` shadow each other) keeps the lexicographically-
    first manifest and emits no error here -- callers that care about
    which copy won should consume the underlying ``Distribution`` list
    directly.  Duplicate ``extension_id`` across different distributions
    is a registry-level concern handled in
    :class:`~lfx.extension.registry.ExtensionRegistry`.
    """
    iterator: Iterable[importlib_metadata.Distribution] = (
        distributions if distributions is not None else importlib_metadata.distributions()
    )

    seen_canonical: set[str] = set()
    extensions: list[DiscoveredExtension] = []
    errors: list[ExtensionError] = []

    for dist in iterator:
        manifest_path = _distribution_manifest_path(dist)
        if manifest_path is None:
            continue

        canonical = _distribution_canonical_name(dist) or manifest_path.parent.name
        if canonical in seen_canonical:
            # Duplicate canonical name (broken venv / shadowed install).
            # Discovery keeps the first; registry can surface duplicate-
            # distribution warnings if the loader cares.
            logger.debug("Skipping duplicate distribution %r at %s", canonical, manifest_path)
            continue
        seen_canonical.add(canonical)

        record, error = _build_installed_record(dist, manifest_path)
        if error is not None:
            errors.append(error)
            continue
        if record is not None:
            extensions.append(record)

    return extensions, errors


# ---------------------------------------------------------------------------
# Seed-directory discovery
# ---------------------------------------------------------------------------


def _resolve_seed_paths(
    *,
    seed_dir_env: str | None,
    default: Path | None,
) -> tuple[list[Path], list[ExtensionError]]:
    """Translate the seed-dir env var and default into a concrete path list.

    Caller-supplied ``seed_dir_env``/``default`` override the live env-var
    lookup so tests don't touch ``os.environ``.

    Behavior:
        * If ``seed_dir_env`` is non-empty, split on ``os.pathsep`` and use
          those paths.  Each missing directory raises a typed
          ``seed-directory-not-found`` error (the operator explicitly
          configured a directory; absence is a misconfiguration).
        * If ``seed_dir_env`` is unset/empty, fall back to ``default``.
          A missing default path is silently skipped: ``/opt/langflow/
          bundles`` rarely exists outside Docker and absence is normal.
    """
    errors: list[ExtensionError] = []
    if seed_dir_env:
        paths: list[Path] = []
        for raw in seed_dir_env.split(os.pathsep):
            stripped = raw.strip()
            if not stripped:
                continue
            candidate = Path(stripped).expanduser()
            if not candidate.is_dir():
                errors.append(
                    ExtensionError(
                        code="seed-directory-not-found",
                        message=f"Seed directory does not exist: {candidate}",
                        location=str(candidate),
                        content=stripped,
                        hint=(
                            "Set LANGFLOW_SEED_DIR to a directory that exists, "
                            "or unset it to fall back to /opt/langflow/bundles."
                        ),
                    )
                )
                continue
            paths.append(candidate)
        return paths, errors

    if default is None:
        return [], errors
    if default.is_dir():
        return [default], errors
    return [], errors


def _iter_seed_subdirectories(seed_root: Path) -> Iterator[Path]:
    """Yield each immediate subdirectory of *seed_root* in deterministic order.

    Hidden directories (``.git``, ``.venv``) and the conventional
    ``__pycache__`` artifact are skipped.  Symlinked subdirectories are
    followed only if their resolved target stays inside ``seed_root`` --
    a symlink pointing anywhere else is silently dropped so the trust
    boundary matches the loader's per-file check
    (see lfx.extension._paths.is_within and loader._discovery.iter_bundle_python_files).
    A dangling link (broken target) is also dropped.
    """
    try:
        children = sorted(seed_root.iterdir(), key=lambda p: p.name)
    except OSError as exc:
        logger.warning("Could not enumerate seed directory %s: %s", seed_root, exc)
        return
    for child in children:
        if child.name.startswith(".") or child.name in SKIP_DIR_NAMES:
            continue
        try:
            if not child.is_dir():
                continue
        except OSError:
            continue
        # Containment check: a symlink pointing outside the seed root must
        # not be treated as a seed-resident bundle. The loader's per-file
        # walk already enforces this for descendant files; we apply the
        # same gate at the directory level so the trust boundary matches.
        if not is_within(child, seed_root):
            logger.warning(
                "Seed subdirectory %s resolves outside %s; skipping symlink-escape candidate.",
                child,
                seed_root,
            )
            continue
        yield child


def _build_seed_record(seed_subdir: Path) -> tuple[DiscoveredExtension | None, ExtensionError | None]:
    """Parse the manifest at *seed_subdir* into a :class:`DiscoveredExtension`.

    A directory without a recognizable manifest is silently skipped: seed
    operators may stage non-extension content alongside bundles.  Anything
    that *looks* like a manifest but fails validation surfaces as a typed
    error so the operator sees the misconfiguration in
    ``lfx extension list``.
    """
    extension_json = seed_subdir / "extension.json"
    pyproject = seed_subdir / "pyproject.toml"
    has_extension_json = extension_json.is_file()
    has_pyproject_section = False
    if not has_extension_json and pyproject.is_file():
        try:
            has_pyproject_section = _pyproject_declares_extension(pyproject)
        except OSError as exc:
            return None, ExtensionError(
                code="manifest-unreadable",
                message=str(exc),
                location=str(pyproject),
                content=seed_subdir.name,
                hint="Check file permissions on the pyproject.toml and re-run.",
            )

    if not has_extension_json and not has_pyproject_section:
        return None, None

    try:
        source = load_manifest(seed_subdir)
    except FileNotFoundError as exc:
        return None, ExtensionError(
            code="manifest-not-found",
            message=str(exc),
            location=str(seed_subdir),
            content=seed_subdir.name,
            hint="Ship an extension.json or a pyproject.toml with [tool.langflow.extension].",
        )
    except (ValueError, TypeError, OSError) as exc:
        return None, ExtensionError(
            code="manifest-invalid",
            message=str(exc),
            location=str(seed_subdir / ("extension.json" if has_extension_json else "pyproject.toml")),
            content=seed_subdir.name,
            hint="Run `lfx extension validate` against the seed subdirectory to see per-field detail.",
        )

    bundle = source.manifest.bundles[0]
    path_error = _verify_bundle_path_safety(seed_subdir, bundle)
    if path_error is not None:
        return None, path_error
    return (
        DiscoveredExtension(
            extension_id=source.manifest.id,
            version=source.manifest.version,
            bundle_name=bundle.name,
            manifest=source,
            source_kind="seed",
            source=str(seed_subdir.resolve(strict=False)),
            extension_root=seed_subdir,
        ),
        None,
    )


def discover_seed_extensions(
    *,
    seed_dir_env: str | None = None,
    default: Path | None = DEFAULT_SEED_DIR,
) -> tuple[list[DiscoveredExtension], list[ExtensionError]]:
    """Scan one or more seed directories for manifest-shipping bundles.

    Args:
        seed_dir_env: Explicit override for ``$LANGFLOW_SEED_DIR``.  Pass
            ``None`` to read the live environment variable; pass an empty
            string to force "unset" behaviour without touching the env.
        default: Path checked when ``seed_dir_env`` is empty.  Defaults to
            :data:`DEFAULT_SEED_DIR` (``/opt/langflow/bundles``).  Pass
            ``None`` to disable the default entirely.

    Returns:
        ``(extensions, errors)``.  ``extensions`` is the flat list across
        every configured seed root.  ``errors`` reports configured-but-
        missing seed roots and per-subdirectory manifest failures.
    """
    if seed_dir_env is None:
        seed_dir_env = os.environ.get(SEED_DIR_ENV_VAR)

    seed_paths, errors = _resolve_seed_paths(seed_dir_env=seed_dir_env, default=default)
    extensions: list[DiscoveredExtension] = []

    for seed_root in seed_paths:
        for subdir in _iter_seed_subdirectories(seed_root):
            record, error = _build_seed_record(subdir)
            if error is not None:
                errors.append(error)
                continue
            if record is not None:
                extensions.append(record)

    return extensions, errors


# ---------------------------------------------------------------------------
# Combined entry point
# ---------------------------------------------------------------------------


def discover_all_extensions(
    *,
    distributions: Iterable[importlib_metadata.Distribution] | None = None,
    seed_dir_env: str | None = None,
    default_seed_dir: Path | None = DEFAULT_SEED_DIR,
) -> tuple[list[DiscoveredExtension], list[ExtensionError]]:
    """Run both production-install discovery passes and merge their results.

    Equivalent to calling :func:`discover_installed_extensions` and
    :func:`discover_seed_extensions`, with one extra responsibility: when a
    seed-directory bundle ships the same ``extension_id`` as an installed
    one, the seed copy is dropped (installed wins by precedence) and a
    ``seed-bundle-shadowed`` :class:`ExtensionError` is emitted so the
    operator can see the shadow instead of silently losing one source.
    Installed records still appear first in the returned list.
    """
    installed, installed_errors = discover_installed_extensions(distributions=distributions)
    seeded, seed_errors = discover_seed_extensions(seed_dir_env=seed_dir_env, default=default_seed_dir)

    installed_ids = {ext.extension_id for ext in installed}
    kept_seeded: list[DiscoveredExtension] = []
    shadow_errors: list[ExtensionError] = []
    for ext in seeded:
        if ext.extension_id in installed_ids:
            shadow_errors.append(
                ExtensionError(
                    code="seed-bundle-shadowed",
                    message=(
                        f"Seed-directory bundle {ext.extension_id!r} at {ext.extension_root} "
                        "is shadowed by an installed Extension of the same name; "
                        "the seed copy is being skipped."
                    ),
                    location=str(ext.extension_root),
                    content=ext.extension_id,
                    hint=(
                        "Uninstall the conflicting distribution or remove the seed "
                        "subdirectory so only one source ships this bundle."
                    ),
                )
            )
            continue
        kept_seeded.append(ext)

    return installed + kept_seeded, installed_errors + seed_errors + shadow_errors

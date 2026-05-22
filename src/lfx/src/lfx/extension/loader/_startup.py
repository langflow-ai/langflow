"""Server-startup discovery flows for installed + seed-directory bundles.

Extracted from ``_orchestrator.py`` so the orchestration core stays under
the structural file-size limit and the two startup flows (which both
delegate to :func:`load_extension` and add cross-source dedupe logic on
top) live in a file dedicated to that concern.

Both functions are re-exported from the loader package so external
imports keep working unchanged.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.extension.errors import ExtensionError
from lfx.extension.loader._orchestrator import load_extension
from lfx.extension.loader._plugins import _resolve_distribution_roots
from lfx.extension.loader._types import SLOT_OFFICIAL, LoadResult

if TYPE_CHECKING:
    from collections.abc import Iterable
    from importlib import metadata as importlib_metadata
    from pathlib import Path


def load_installed_extensions(
    distributions: Iterable[importlib_metadata.Distribution] | None = None,
) -> list[LoadResult]:
    """Discover all installed Extensions and load them at the @official slot.

    Startup-time discovery flow: walks every distribution in ``distributions``
    (defaults to the live environment), finds those that ship a v0 manifest,
    and calls :func:`load_extension` on each of their package roots.

    Cross-source bundle-name dedupe across installed distributions: two
    distributions with different canonical names but identical ``bundle.name``
    both land at @official under ``_lfx_ext.official.<name>.*`` and silently
    clobber each other in sys.modules.  The check below surfaces a typed
    ``duplicate-bundle-name`` error on the losing record and drops its
    components.

    Two distributions sharing a canonical name (broken venv) are resolved
    by lexicographically-first manifest path (the "winner") and surface a
    typed ``duplicate-distribution`` error on the winner's
    :class:`LoadResult`.

    Args:
        distributions: Override the distribution iterator (test seam).
            Defaults to ``importlib.metadata.distributions()``.

    Returns:
        One :class:`LoadResult` per unique canonical distribution name.
        Order is lexicographic by canonical name for determinism.
    """
    resolved = _resolve_distribution_roots(distributions)
    results: list[LoadResult] = []
    seen_bundles: dict[str, LoadResult] = {}
    for canonical in sorted(resolved):
        winner_root, manifests = resolved[canonical]
        result = load_extension(winner_root, slot=SLOT_OFFICIAL, distribution=canonical)
        if len(manifests) > 1:
            paths_csv = ", ".join(str(m) for m in manifests)
            result.errors.append(
                ExtensionError(
                    code="duplicate-distribution",
                    message=(
                        f"Two installed distributions share the canonical name {canonical!r}; "
                        f"loading from {manifests[0]} and ignoring the others."
                    ),
                    location=paths_csv,
                    content=canonical,
                    hint=(
                        "Uninstall the duplicate distribution(s) or rename one so each canonical "
                        "name maps to a single installed package."
                    ),
                )
            )
        if result.bundle and result.components:
            existing = seen_bundles.get(result.bundle)
            if existing is not None:
                result.errors.append(
                    ExtensionError(
                        code="duplicate-bundle-name",
                        message=(
                            f"Bundle {result.bundle!r} from distribution {canonical!r} collides "
                            f"with a bundle of the same name already loaded from "
                            f"{existing.distribution or existing.source_path}; the second loader "
                            "is being dropped to prevent silent sys.modules clobber at "
                            "_lfx_ext.official.<bundle>.*."
                        ),
                        location=str(result.source_path) if result.source_path else result.bundle,
                        content=result.bundle,
                        hint=(
                            "Rename one of the bundles so each bundle.name maps to exactly one "
                            "installed distribution; cross-source @official-slot bundle names "
                            "must be unique."
                        ),
                    )
                )
                result.components = []
            else:
                seen_bundles[result.bundle] = result
        results.append(result)
    return results


def load_seed_extensions(
    *,
    seed_dir_env: str | None = None,
    default_seed_dir: Path | None = None,
) -> list[LoadResult]:
    """Discover seed-directory Extensions and load them at the @official slot.

    The "seed directory" is the filesystem source documented in the
    deployment guide where an operator stages bundles for startup without
    going through pip.  Default location is ``/opt/langflow/bundles``;
    override via ``$LANGFLOW_SEED_DIR``.  Each immediate subdirectory that
    ships a v0 manifest becomes one Extension at the @official slot.

    Args:
        seed_dir_env: Test seam.  ``None`` reads ``$LANGFLOW_SEED_DIR``
            from the live environment; pass an explicit string to bypass
            ``os.environ``.
        default_seed_dir: Test seam.  ``None`` uses the discovery layer's
            default (``/opt/langflow/bundles``); pass an explicit ``Path``
            to override or ``Path("/dev/null")`` to disable the default.

    Returns:
        One :class:`LoadResult` per seed-resident Extension, plus one
        sentinel :class:`LoadResult` per discovery-time error
        (``seed-directory-not-found``, ``manifest-invalid``, ...) so the
        existing diagnostics emitter surfaces the failure without dropping
        the typed payload.  Order is sorted by seed-subdirectory path for
        determinism.
    """
    from lfx.extension.discovery import DEFAULT_SEED_DIR, discover_seed_extensions

    if default_seed_dir is None:
        default_seed_dir = DEFAULT_SEED_DIR

    discovered, errors = discover_seed_extensions(
        seed_dir_env=seed_dir_env,
        default=default_seed_dir,
    )

    results: list[LoadResult] = []

    for err in errors:
        sentinel = LoadResult(slot=None, source_path=None, distribution=None)
        sentinel.errors.append(err)
        results.append(sentinel)

    for record in sorted(discovered, key=lambda r: str(r.extension_root)):
        result = load_extension(
            record.extension_root,
            slot=SLOT_OFFICIAL,
            distribution=None,
        )
        results.append(result)

    return results

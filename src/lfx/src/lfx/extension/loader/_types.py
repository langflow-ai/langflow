"""Public dataclasses and slot constants for the extension loader.

Kept module-level so consumers (events pipeline, registry, tests) can import
them without paying the cost of dragging in the discovery / detection /
orchestrator code.  These types are part of the loader's stable surface;
the underscore-prefixed siblings are not.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from pathlib import Path

    from lfx.extension.errors import ExtensionError

# ---------------------------------------------------------------------------
# Slot names
# ---------------------------------------------------------------------------

SLOT_OFFICIAL: Literal["official"] = "official"
"""Slot for installed Extensions (pip install / manifest-shipping distribution)."""

SLOT_EXTRA: Literal["extra"] = "extra"
"""Slot for loose LANGFLOW_COMPONENTS_PATH directories (ad-hoc local dev)."""

SLOT_VALUES: tuple[str, ...] = (SLOT_OFFICIAL, SLOT_EXTRA)
"""All slot names accepted by ``load_extension``.  Public so test suites can
parametrize over the full set without re-listing it."""


# ---------------------------------------------------------------------------
# LoadedComponent
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LoadedComponent:
    """A successfully loaded Component class plus its registry coordinates.

    Frozen so callers can place these in sets / dicts and emit them across
    the events pipeline without worrying about mutation.

    The :attr:`namespaced_id` is the canonical address used by saved flows
    after the migration table rewrites legacy references.

    Slot / distribution invariant
    -----------------------------
    ``@extra`` components MUST NOT carry a ``distribution``: they're loose
    folders from ``LANGFLOW_COMPONENTS_PATH``, never pip-installed. The
    reverse (``@official`` with ``distribution=None``) is permitted because
    ``load_extension`` is used for dev-mode loads against a working tree
    *before* the package gets installed (the ``extension dev`` flow);
    only ``load_installed_extensions`` is required to carry a canonical
    PEP-503 name through. Enforced in :meth:`__post_init__` so the rule
    travels with the type when reload and startup discovery construct
    :class:`LoadedComponent` directly.
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
    package; ``None`` for inline LANGFLOW_COMPONENTS_PATH bundles AND for
    @official dev-mode loads against a not-yet-installed working tree."""
    source_hash: str = ""
    """SHA-256 hex digest of ``file_path`` bytes at load time.  Empty string
    means the loader did not stamp a hash (test fixtures, legacy callers).
    Used by :func:`lfx.extension.reload._diff` to detect in-class edits
    where the class-name set is unchanged but the backing source changed --
    without this, body edits surface to the API as ``components_added=[]``
    / ``components_removed=[]`` and the UI shows ``no component changes``."""

    def __post_init__(self) -> None:
        if self.slot == SLOT_EXTRA and self.distribution is not None:
            msg = (
                f"LoadedComponent {self.bundle}:{self.class_name} is at @extra "
                f"slot but carries distribution={self.distribution!r}; @extra "
                "components are loose folders and must not have a distribution."
            )
            raise ValueError(msg)

    @property
    def namespaced_id(self) -> str:
        """The ``ext:<bundle>:<Class>@<slot>`` registry address."""
        return f"ext:{self.bundle}:{self.class_name}@{self.slot}"


# ---------------------------------------------------------------------------
# LoadResult
# ---------------------------------------------------------------------------


@dataclass
class LoadResult:
    """Outcome of a single load_extension or inline-bundle load.

    ``components`` is the registry payload on success; ``errors`` carries
    typed failures.  ``ok`` is the single bit downstream code should branch
    on (e.g. the events pipeline emits ``extension_loaded`` when ``ok`` and
    ``extension_error`` otherwise).

    Partial-success contract
    ------------------------
    ``components`` MAY be non-empty when ``errors`` is non-empty -- this
    represents a partial load where some bundle modules imported cleanly
    but others failed (e.g. one ``module-import-failed`` plus three
    successfully-registered classes from sibling files). Callers that only
    branch on ``ok`` get strict success; callers that want to surface
    "partial X of Y loaded" diagnostics should consume ``components`` and
    ``errors`` together. The future events pipeline is expected to fan
    out as: ``extension_loaded`` when ``ok``, ``extension_error`` when not,
    plus per-component ``component_registered`` events for everything in
    ``components`` regardless of ``ok``.

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

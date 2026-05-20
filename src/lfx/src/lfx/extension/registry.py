"""Read-only Extension registry for production-install sources.

Where :mod:`lfx.extension.discovery` *finds* manifest-shipping packages
and seed directories, this module *registers* them: it owns the in-memory
state that ``lfx extension list`` (and, downstream, the loader and the
events pipeline) read from.

Every registered Extension lives at the ``@official`` slot in this
milestone.  Two source kinds reach the registry:

    * **installed** -- a pip-installed distribution shipping a manifest.
      Installed at image-build time in Mode B/C, at ``pip install`` time
      in Mode A.

    * **seed** -- an immediate subdirectory of a seed root (default
      ``/opt/langflow/bundles``, overridable via ``$LANGFLOW_SEED_DIR``).
      Used by Docker images that prefer an explicit on-disk layout.

Both source kinds are **immutable at runtime**.  ``autoUpdate`` is
forced ``False`` for installed/seed Extensions; any mutation verb
exposed by the service layer (uninstall, disable, enable, install,
update) raises :class:`ExtensionImmutableError` carrying a typed
:class:`~lfx.extension.errors.ExtensionError` with code
``installed-extension-immutable`` or ``seed-directory-immutable``.

Mutation verbs are exposed at the *service* layer here so the invariant
is testable today, but the **CLI** uninstall surface is a follow-up.
Routes that try to mount these as HTTP handlers are blocked by the
router-trust CI guard.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from threading import RLock
from typing import TYPE_CHECKING, Literal

from lfx.extension.errors import ExtensionError

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

    from lfx.extension.discovery import DiscoveredExtension, SourceKind
    from lfx.extension.manifest import ManifestSource


# ---------------------------------------------------------------------------
# LoadStatus
# ---------------------------------------------------------------------------


class LoadStatus(str, Enum):
    """Lifecycle state surfaced through ``lfx extension list``.

    Discovery alone produces ``DISCOVERED``; the component loader flips
    entries to ``LOADED`` once their components register, and to
    ``FAILED`` on any per-bundle import error.  Keeping the enum here --
    rather than in the loader -- means ``extension list`` can render the
    full life-cycle without a circular import.
    """

    DISCOVERED = "discovered"
    LOADED = "loaded"
    FAILED = "failed"

    def __str__(self) -> str:  # pragma: no cover - enum convenience
        return self.value


# ---------------------------------------------------------------------------
# Extension
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Extension:
    """A registered Extension at the @official slot.

    Frozen so the registry can hand instances out without callers
    accidentally mutating shared state.  The registry holds the
    authoritative copy and replaces (rather than mutates) entries when
    state changes -- e.g. when the loader marks a bundle ``LOADED``.

    The slot is a stored field (not a property) because we expect future
    milestones to extend the registry with additional slots, and locking
    the field shape now keeps serialization stable.
    """

    extension_id: str
    version: str
    bundle_name: str
    slot: Literal["official"]
    source_kind: SourceKind
    source: str
    extension_root: Path
    manifest: ManifestSource
    auto_update: bool = False
    load_status: LoadStatus = LoadStatus.DISCOVERED
    load_error: ExtensionError | None = None

    @property
    def namespaced_slot(self) -> str:
        """Slot rendered with the canonical ``@`` prefix (e.g. ``@official``).

        Convenience for human-readable output (``extension list`` and the
        events pipeline).  The stored :attr:`slot` keeps the bare token
        so collection keys stay simple.
        """
        return f"@{self.slot}"


# ---------------------------------------------------------------------------
# ExtensionImmutableError
# ---------------------------------------------------------------------------


class ExtensionImmutableError(RuntimeError):
    """Raised when a caller tries to mutate an installed or seed Extension.

    Wraps a typed :class:`~lfx.extension.errors.ExtensionError` so HTTP
    callers can surface ``error.to_dict()`` directly and CLI callers can
    feed the same object into ``format_extension_error``.

    The wrapped code is one of:
        * ``installed-extension-immutable`` -- the entry came from a
          pip-installed distribution; mutate the install (rebuild the
          image, change the lockfile) instead of poking the runtime.
        * ``seed-directory-immutable`` -- the entry came from a seed
          subdirectory; mutate the directory layout, not the runtime.
    """

    def __init__(self, error: ExtensionError) -> None:
        super().__init__(error.message)
        self.error = error

    def to_dict(self) -> dict[str, object]:
        """Forward to :meth:`ExtensionError.to_dict` for HTTP/JSON output."""
        return self.error.to_dict()


# ---------------------------------------------------------------------------
# ExtensionRegistry
# ---------------------------------------------------------------------------


@dataclass
class _RegistryEntry:
    """Internal mutable wrapper so the registry can swap in updated state.

    Public consumers never see this; :meth:`ExtensionRegistry.list` and
    :meth:`ExtensionRegistry.get` always return the frozen
    :class:`Extension` snapshot via :attr:`extension`.
    """

    extension: Extension


class ExtensionRegistry:
    """Service-layer registry for installed and seed Extensions.

    Thread-safe (operations are guarded by a re-entrant lock so the
    loader can call back into the registry from within
    :meth:`mark_loaded` /``mark_failed`` without deadlocking).

    The registry is *additive* at startup: discovery results are pinned
    in via :meth:`register_installed` / :meth:`register_seed` and never
    leave the registry until the process exits.  Mutation verbs exist
    only to enforce the immutability invariant.
    """

    def __init__(self) -> None:
        self._entries: dict[str, _RegistryEntry] = {}
        self._lock = RLock()

    # ------------------------------------------------------------------
    # Read API
    # ------------------------------------------------------------------

    def list_extensions(self) -> list[Extension]:
        """Return every registered Extension in registration order.

        Insertion order is preserved (Python's ``dict`` is ordered) so
        ``lfx extension list`` produces stable output even when the
        underlying source iterators do not.
        """
        with self._lock:
            return [entry.extension for entry in self._entries.values()]

    def get(self, extension_id: str) -> Extension | None:
        """Return the registered Extension by id, or ``None`` if absent."""
        with self._lock:
            entry = self._entries.get(extension_id)
            return entry.extension if entry is not None else None

    def __contains__(self, extension_id: str) -> bool:
        with self._lock:
            return extension_id in self._entries

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)

    # ------------------------------------------------------------------
    # Registration (called from startup discovery)
    # ------------------------------------------------------------------

    def register_installed(self, discovered: DiscoveredExtension) -> Extension:
        """Pin an installed-package Extension into the registry.

        Raises:
            ValueError: ``discovered.source_kind`` is not ``installed``
                (callers should route seed entries through
                :meth:`register_seed`).
        """
        if discovered.source_kind != "installed":
            msg = f"register_installed received source_kind={discovered.source_kind!r}; expected 'installed'."
            raise ValueError(msg)
        return self._register(discovered)

    def register_seed(self, discovered: DiscoveredExtension) -> Extension:
        """Pin a seed-directory Extension into the registry.

        Raises:
            ValueError: ``discovered.source_kind`` is not ``seed``.
        """
        if discovered.source_kind != "seed":
            msg = f"register_seed received source_kind={discovered.source_kind!r}; expected 'seed'."
            raise ValueError(msg)
        return self._register(discovered)

    def _register(self, discovered: DiscoveredExtension) -> Extension:
        """Internal registration path shared by installed and seed."""
        extension = Extension(
            extension_id=discovered.extension_id,
            version=discovered.version,
            bundle_name=discovered.bundle_name,
            slot=discovered.slot,
            source_kind=discovered.source_kind,
            source=discovered.source,
            extension_root=discovered.extension_root,
            manifest=discovered.manifest,
            auto_update=False,  # installed/seed Extensions never auto-update
            load_status=LoadStatus.DISCOVERED,
        )
        with self._lock:
            existing = self._entries.get(extension.extension_id)
            if existing is not None:
                msg = (
                    f"Extension {extension.extension_id!r} already registered "
                    f"from {existing.extension.source_kind} source "
                    f"{existing.extension.source!r}; refusing to register "
                    f"{extension.source_kind} source {extension.source!r}."
                )
                raise DuplicateExtensionError(
                    ExtensionError(
                        code="duplicate-extension-id",
                        message=msg,
                        location=existing.extension.source,
                        content=extension.extension_id,
                        hint=(
                            "Each extension id must be registered exactly once. "
                            "Pick one source: a pip install or a seed directory."
                        ),
                    )
                )
            self._entries[extension.extension_id] = _RegistryEntry(extension=extension)
            return extension

    # ------------------------------------------------------------------
    # Load-state updates (called from the loader once it lands)
    # ------------------------------------------------------------------

    def mark_loaded(self, extension_id: str) -> Extension:
        """Flip an entry's :attr:`load_status` to ``LOADED``.

        Used by the component loader once a bundle's components have
        successfully registered.  This is *not* a mutation of the
        immutability surface -- the install record itself is unchanged;
        we're recording the side effect of loading the install.
        """
        return self._replace_status(extension_id, status=LoadStatus.LOADED, error=None)

    def mark_failed(self, extension_id: str, error: ExtensionError) -> Extension:
        """Flip an entry's :attr:`load_status` to ``FAILED`` with *error* attached.

        Same rationale as :meth:`mark_loaded`: this records the loader's
        observation, not a mutation of the install.
        """
        return self._replace_status(extension_id, status=LoadStatus.FAILED, error=error)

    def _replace_status(
        self,
        extension_id: str,
        *,
        status: LoadStatus,
        error: ExtensionError | None,
    ) -> Extension:
        with self._lock:
            entry = self._entries.get(extension_id)
            if entry is None:
                msg = f"Cannot update load status: no Extension registered with id {extension_id!r}."
                raise KeyError(msg)
            updated = Extension(
                extension_id=entry.extension.extension_id,
                version=entry.extension.version,
                bundle_name=entry.extension.bundle_name,
                slot=entry.extension.slot,
                source_kind=entry.extension.source_kind,
                source=entry.extension.source,
                extension_root=entry.extension.extension_root,
                manifest=entry.extension.manifest,
                auto_update=entry.extension.auto_update,
                load_status=status,
                load_error=error,
            )
            entry.extension = updated
            return updated

    # ------------------------------------------------------------------
    # Mutation surface (always raises for installed/seed in this milestone)
    # ------------------------------------------------------------------

    def uninstall(self, extension_id: str) -> None:
        """Refuse to uninstall an installed/seed Extension.

        Always raises :class:`ExtensionImmutableError`.  The CLI verb
        lands in B4; this method exists today so the invariant is
        testable.
        """
        self._refuse_mutation(extension_id, verb="uninstall")

    def disable(self, extension_id: str) -> None:
        """Refuse to disable an installed/seed Extension."""
        self._refuse_mutation(extension_id, verb="disable")

    def enable(self, extension_id: str) -> None:
        """Refuse to enable an installed/seed Extension."""
        self._refuse_mutation(extension_id, verb="enable")

    def install(self, extension_id: str) -> None:
        """Refuse to install via the runtime registry service.

        Production install in this milestone is ``pip install`` in a
        Dockerfile, never a runtime call.  The router-trust CI guard
        blocks any HTTP handler that tries to mount this verb.
        """
        self._refuse_mutation(extension_id, verb="install")

    def update_entry(self, extension_id: str, **changes: object) -> None:
        """Refuse to mutate an installed/seed Extension's metadata.

        Distinct from :meth:`mark_loaded` / :meth:`mark_failed`, which
        record load-state transitions: ``update_entry`` rejects edits to
        the install record itself (auto_update, source, version, ...).
        Always raises.
        """
        # ``changes`` is captured so the rejection message can mention
        # what the caller tried to change, but we don't actually need to
        # process it -- every change is refused.
        del changes
        self._refuse_mutation(extension_id, verb="update")

    def _refuse_mutation(self, extension_id: str, *, verb: str) -> None:
        with self._lock:
            entry = self._entries.get(extension_id)
            if entry is None:
                msg = f"Cannot {verb}: no Extension registered with id {extension_id!r}."
                raise KeyError(msg)
            extension = entry.extension

        if extension.source_kind == "installed":
            code = "installed-extension-immutable"
            hint = (
                f"To {verb} {extension_id!r}, change the pip install "
                "(remove the package from the image / lockfile) and restart Langflow. "
                "Runtime mutation of installed Extensions is intentionally not supported."
            )
        elif extension.source_kind == "seed":
            code = "seed-directory-immutable"
            hint = (
                f"To {verb} {extension_id!r}, edit the seed directory layout and "
                "restart Langflow. Runtime mutation of seed Extensions is intentionally not supported."
            )
        else:  # pragma: no cover - defensive: every source_kind is covered above
            msg = f"Unknown source_kind {extension.source_kind!r} on Extension {extension_id!r}."
            raise RuntimeError(msg)

        error = ExtensionError(
            code=code,
            message=(
                f"Refusing to {verb} Extension {extension_id!r} from "
                f"{extension.source_kind} source {extension.source!r}."
            ),
            location=extension.source,
            content=extension_id,
            hint=hint,
        )
        raise ExtensionImmutableError(error)


# ---------------------------------------------------------------------------
# DuplicateExtensionError
# ---------------------------------------------------------------------------


class DuplicateExtensionError(RuntimeError):
    """Raised when two sources claim the same ``extension_id``.

    Distinct from :class:`ExtensionImmutableError` so callers can branch
    on the failure mode: an immutability error means "stop trying to
    mutate the runtime" while a duplicate means "fix the install layout".
    """

    def __init__(self, error: ExtensionError) -> None:
        super().__init__(error.message)
        self.error = error

    def to_dict(self) -> dict[str, object]:
        return self.error.to_dict()


# ---------------------------------------------------------------------------
# Convenience: build a registry directly from discovery results
# ---------------------------------------------------------------------------


def build_registry_from_discovery(
    extensions: Iterable[DiscoveredExtension],
) -> tuple[ExtensionRegistry, list[ExtensionError]]:
    """Construct a fresh registry and pin every *extensions* entry.

    Convenience for the server-startup path: discovery hands the list
    over and the result is a registry plus any duplicate-id errors that
    surfaced.  Per-source errors from discovery itself are *not* re-
    emitted here; the caller has already received them as the discovery
    return value.
    """
    registry = ExtensionRegistry()
    errors: list[ExtensionError] = []
    for ext in extensions:
        try:
            if ext.source_kind == "installed":
                registry.register_installed(ext)
            else:
                registry.register_seed(ext)
        except DuplicateExtensionError as exc:
            errors.append(exc.error)
    return registry, errors

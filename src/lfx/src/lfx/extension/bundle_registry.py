"""In-memory component registry for installed Bundles.

The :class:`BundleRegistry` is the single piece of mutable shared state the
Extension System owns at runtime.  It maps a Bundle name to a frozen record
of the components that Bundle currently exposes, and serializes mutation so
the atomic-swap reload pipeline (see :mod:`lfx.extension.reload`) can update
one Bundle without races.

Concurrency model
-----------------

Two locks live on the registry:

* ``_write_lock`` (a re-entrant ``threading.Lock``) covers every mutation.
  Read paths take a quick lock to copy out a snapshot, then release; they
  hold it for the duration of a dict copy, never longer.

* ``_in_progress`` is a ``set[str]`` of bundle names that currently have a
  reload running.  The reload core acquires :meth:`begin_reload` before
  Stage 1 and releases it via :meth:`finish_reload` (or the
  :meth:`reload_in_progress` context manager) after Stage 5.  A second
  reload attempt for the same bundle while one is in flight raises
  :class:`ReloadInProgressError` so the caller can return a typed
  ``reload-in-progress`` response.

Snapshots returned by :meth:`snapshot` / :meth:`get_bundle` /
:meth:`list_components` are *immutable views*: ``BundleRecord`` is frozen
and ``LoadedComponent`` is frozen, so callers cannot mutate the registry
through the snapshot.  This is the property the concurrent-read tests rely
on -- a reader holding a snapshot from before Stage 3 sees the pre-swap
class set even after Stage 3 has flipped the registry's internal pointer.

Slot semantics
--------------

The registry stores both ``official`` and ``extra`` slot bundles in the
same map keyed by bundle name.  Bundle names are unique across slots in
v0; the component loader and ``discover_inline_bundles`` both enforce
this upstream so the registry does not need to disambiguate by slot.
"""

from __future__ import annotations

import json
import logging
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path
    from typing import Literal

    from lfx.extension.loader import LoadedComponent


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ReloadInProgressError(RuntimeError):
    """Raised when a second reload is requested for a Bundle already mid-reload.

    Carries the ``bundle`` name so the API layer can put it in the typed
    error body without parsing a string.
    """

    def __init__(self, bundle: str) -> None:
        super().__init__(f"reload already in progress for bundle {bundle!r}")
        self.bundle = bundle


# ---------------------------------------------------------------------------
# BundleRecord
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BundleRecord:
    """Immutable snapshot of a Bundle's registered components.

    The reload pipeline builds a brand-new ``BundleRecord`` in Stage 1+2 and
    swaps it into the registry in Stage 3.  In-flight code paths that hold
    a reference to the *previous* ``BundleRecord`` keep operating against
    the pre-swap class set; this is the property the in-flight-flow test
    relies on.
    """

    bundle: str
    extension_id: str
    extension_version: str
    slot: Literal["official", "extra"]
    components: tuple[LoadedComponent, ...] = ()
    distribution: str | None = None
    source_path: Path | None = None

    @property
    def class_names(self) -> frozenset[str]:
        """Set of component class names in this bundle."""
        return frozenset(c.class_name for c in self.components)

    def by_class_name(self) -> dict[str, LoadedComponent]:
        """Return ``{class_name: LoadedComponent}`` for this bundle."""
        return {c.class_name: c for c in self.components}


# ---------------------------------------------------------------------------
# BundleRegistry
# ---------------------------------------------------------------------------


class BundleRegistry:
    """Thread-safe registry of installed Bundles, keyed by bundle name.

    Designed for many concurrent readers and one writer at a time.  All
    mutations go through the write lock; reads take the lock just long
    enough to copy out an immutable snapshot.

    The registry can optionally persist a flat ``components_index.json``
    after every write so external tooling (the dev server, the CLI status
    command) can introspect the live set without poking into the process.
    Pass ``index_path`` at construction time to enable.
    """

    def __init__(self, *, index_path: Path | None = None) -> None:
        self._write_lock = threading.RLock()
        self._bundles: dict[str, BundleRecord] = {}
        self._in_progress: set[str] = set()
        self._index_path: Path | None = index_path

    # -- read paths ----------------------------------------------------------

    def snapshot(self) -> dict[str, BundleRecord]:
        """Return a shallow copy of the bundle map.

        ``BundleRecord`` is frozen, so the copy is safe to hand out without
        defensive cloning.  Callers iterating across a long-running flow
        should grab one snapshot at the start and reuse it; the registry
        does not guarantee that two consecutive ``snapshot()`` calls return
        the same dict.
        """
        with self._write_lock:
            return dict(self._bundles)

    def get_bundle(self, bundle: str) -> BundleRecord | None:
        with self._write_lock:
            return self._bundles.get(bundle)

    def list_components(self) -> list[LoadedComponent]:
        """Flatten every bundle's components into one list.

        Order: bundle names sorted lexicographically, then component order
        within each bundle (preserved from the loader).  Stable so the
        components_index.json output is reproducible.
        """
        snap = self.snapshot()
        out: list[LoadedComponent] = []
        for name in sorted(snap):
            out.extend(snap[name].components)
        return out

    # -- write paths ---------------------------------------------------------

    @contextmanager
    def write_locked(self) -> Iterator[None]:
        """Hold the registry write lock across multiple mutations.

        The lock is the same ``RLock`` :meth:`install_bundle` /
        :meth:`remove_bundle` acquire internally, so callers can wrap a
        compound atomic operation -- e.g. swapping ``sys.modules`` and
        installing the new ``BundleRecord`` together -- without the
        registry briefly exposing a state where one half has flipped and
        the other has not.  The reentrant acquire inside the inner
        write methods is a no-op while this context is active.

        The reload pipeline uses this so concurrent readers can never
        observe new ``sys.modules`` entries with the old ``BundleRecord``
        (or vice versa).
        """
        with self._write_lock:
            yield

    def install_bundle(self, record: BundleRecord) -> BundleRecord | None:
        """Insert or replace a Bundle's record.

        Returns the *previous* record if one existed (so the reload caller
        can compute added/removed components), or ``None`` for a fresh
        install.  Concurrent reads observe either the old record or the
        new record, never a partial state.

        Silent-overwrite detection: when an existing record is replaced
        by a record originating from a different source path (i.e. not a
        reload of the same install but a cross-source bundle-name clash
        that the precedence resolver missed), the overwrite is logged at
        WARNING so an operator sees the collision in the server log even
        if upstream shadow resolution dropped the typed warning.  The
        reload pipeline overwrites the same source_path repeatedly and
        is intentionally silent in that case.
        """
        with self._write_lock:
            previous = self._bundles.get(record.bundle)
            if previous is not None and previous.source_path != record.source_path:
                logger.warning(
                    "bundle_registry: bundle %r is being overwritten by a different source "
                    "(was %s [%s], now %s [%s]); upstream shadow resolver should have caught this. "
                    "The last writer wins, but this typically indicates a cross-source bundle-name "
                    "collision that needs operator attention.",
                    record.bundle,
                    previous.source_path,
                    previous.distribution or previous.slot,
                    record.source_path,
                    record.distribution or record.slot,
                )
            self._bundles[record.bundle] = record
            self._write_index_locked()
            return previous

    def remove_bundle(self, bundle: str) -> BundleRecord | None:
        """Drop a Bundle from the registry.

        Returns the removed record, or ``None`` if it was not present.
        """
        with self._write_lock:
            previous = self._bundles.pop(bundle, None)
            if previous is not None:
                self._write_index_locked()
            return previous

    # -- reload-in-progress guard -------------------------------------------

    def begin_reload(self, bundle: str) -> None:
        """Mark a Bundle as mid-reload, raising if one is already in flight."""
        with self._write_lock:
            if bundle in self._in_progress:
                raise ReloadInProgressError(bundle)
            self._in_progress.add(bundle)

    def finish_reload(self, bundle: str) -> None:
        """Clear the mid-reload marker.  Idempotent: silent if not set."""
        with self._write_lock:
            self._in_progress.discard(bundle)

    @contextmanager
    def reload_in_progress(self, bundle: str) -> Iterator[None]:
        """Context manager pairing :meth:`begin_reload` / :meth:`finish_reload`.

        Always clears the marker on exit, even if the ``with`` body raises.
        """
        self.begin_reload(bundle)
        try:
            yield
        finally:
            self.finish_reload(bundle)

    def is_reload_in_progress(self, bundle: str) -> bool:
        with self._write_lock:
            return bundle in self._in_progress

    # -- components_index.json ----------------------------------------------

    def _write_index_locked(self) -> None:
        """Write ``components_index.json`` while holding the write lock.

        Tolerates filesystem errors silently: the index file is a cache,
        not a source of truth, and a transient write failure must not
        abort an otherwise-successful registry mutation.  A future
        ``extension status`` CLI surfaces stale indexes.
        """
        if self._index_path is None:
            return
        payload = {
            "bundles": [
                {
                    "name": rec.bundle,
                    "extension_id": rec.extension_id,
                    "extension_version": rec.extension_version,
                    "slot": rec.slot,
                    "distribution": rec.distribution,
                    "source_path": str(rec.source_path) if rec.source_path else None,
                    "components": [
                        {
                            "class_name": c.class_name,
                            "namespaced_id": c.namespaced_id,
                            "module_name": c.module_name,
                            "file_path": str(c.file_path),
                        }
                        for c in rec.components
                    ],
                }
                for rec in (self._bundles[name] for name in sorted(self._bundles))
            ],
        }
        try:
            self._index_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._index_path.with_suffix(self._index_path.suffix + ".tmp")
            tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
            tmp.replace(self._index_path)
        except OSError as exc:
            # Cache miss only -- next successful write replaces it.  Log at
            # WARNING so a persistent permission / disk-full failure is not
            # invisible to an operator wondering why the index never updates.
            logger.warning("failed to write components_index.json at %s: %s", self._index_path, exc)


# ---------------------------------------------------------------------------
# Process-wide default registry
# ---------------------------------------------------------------------------


_default_registry: BundleRegistry | None = None
_default_registry_lock = threading.Lock()


def get_default_registry() -> BundleRegistry:
    """Return the lazily-created process-wide registry.

    The HTTP endpoint and CLI both target this registry by default; tests
    construct fresh registries directly so they do not bleed state.  A
    future startup-time install at the @official slot will replace this
    lazy initializer; until then the registry begins empty.
    """
    global _default_registry  # noqa: PLW0603
    with _default_registry_lock:
        if _default_registry is None:
            _default_registry = BundleRegistry()
        return _default_registry


def reset_default_registry() -> None:
    """Drop the process-wide registry (test-only).

    Calling this in normal application code throws away component state and
    should never be necessary.
    """
    global _default_registry  # noqa: PLW0603
    with _default_registry_lock:
        _default_registry = None

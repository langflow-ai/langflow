"""Atomic-swap Bundle reload pipeline (LE-1018).

The :func:`reload_bundle` function is the single entry point for replacing
a Bundle's component set in-place under load.  It runs five clearly-marked
stages and is the *only* code path that mutates the live
:class:`~lfx.extension.registry.BundleRegistry`.

The five stages
---------------

1. **Stage 1 -- parallel load** into a per-reload staging namespace
   (``__reload_staging__.<reload_id>``).  Uses the LE-1015 loader with
   ``module_namespace`` overridden so that the new modules land in
   ``sys.modules`` without colliding with the live ``_lfx_ext.*`` entries.

2. **Stage 2 -- validate** the staging result.  Any error from the loader
   (manifest invalid, import failure, duplicate class names, etc.) aborts
   the reload here.  The live registry is untouched and a
   ``bundle_reload_failed`` event is emitted (currently stubbed; LE-1017).

3. **Stage 3 -- atomic swap** under the registry's write lock.  This is
   the only stage that mutates shared state.  Old ``sys.modules`` entries
   for the bundle are dropped; staging entries are renamed into the live
   ``_lfx_ext.*`` namespace; the new :class:`BundleRecord` is installed.
   Concurrent readers see either fully pre- or fully post-reload state.

4. **Stage 4 -- cleanup** of any leftover ``__reload_staging__.<id>.*``
   modules that did not survive the rename (e.g. import failures partway
   through).  Best-effort: failure here logs but does not roll back.

5. **Stage 5 -- emit** a ``bundle_reloaded`` event with the
   ``components_added`` / ``components_removed`` deltas.  Currently a
   structured-log shim; LE-1017 will swap the body to the real
   ``ExtensionEventsService``.

Concurrency invariants
----------------------

* The registry's :meth:`reload_in_progress` guard prevents a second
  reload for the same Bundle from starting while one is in flight.  The
  second caller raises :class:`ReloadInProgressError`, which the
  HTTP / CLI layers translate into a typed ``reload-in-progress`` error.

* In-flight flows that captured a class reference before Stage 3 keep
  operating against the pre-swap class.  Python won't garbage-collect a
  class while live references exist, so dropping the old module entry
  from ``sys.modules`` does not yank the rug out from under the running
  flow.

* New flows starting *during* Stages 1-2 read the registry snapshot and
  see the old class set.  New flows starting after Stage 3 see the new
  set.  There is no observable mixed state.

Mode A only
-----------

This pipeline only applies to Mode A (in-process Python install).  In
Mode B/C the bundle code lives in a different container image; reload
there means rebuilding the image, not calling this function.  The HTTP
endpoint and CLI both gate on Mode A; if you find yourself reaching into
this module from a non-Mode-A path, stop and re-read LE-905 first.
"""

from __future__ import annotations

import contextlib
import logging
import sys
import uuid
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING

from lfx.extension.bundle_registry import (
    BundleRecord,
    BundleRegistry,
    ReloadInProgressError,
)
from lfx.extension.errors import ExtensionError
from lfx.extension.loader import (
    DEFAULT_MODULE_NAMESPACE,
    SLOT_EXTRA,
    SLOT_OFFICIAL,
    LoadedComponent,
    LoadResult,
    load_extension,
    load_inline_bundle,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from typing import Literal

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Post-swap hooks
# ---------------------------------------------------------------------------
#
# Layers above lfx (the langflow component cache; eventually the events
# service) need to react to a successful reload.  ``lfx`` cannot import
# ``langflow``, so we expose a tiny registration API: ``langflow`` calls
# :func:`register_post_swap_hook` at startup; this module calls every
# registered hook in Stage 5 with the new BundleRecord.  Hooks must be
# fast and exception-tolerant -- we wrap calls in ``logger.exception`` so
# one bad subscriber does not break reload.

_POST_SWAP_HOOKS: list[Callable[[BundleRecord], None]] = []


def register_post_swap_hook(hook: Callable[[BundleRecord], None]) -> None:
    """Register a callback to fire after a successful Stage-3 swap.

    Idempotent: registering the same callable twice is a no-op.  The
    canonical use case is the langflow component cache, which needs to
    rebuild its templates for the bundle so the palette / new-graph path
    sees post-reload classes without a server restart.
    """
    if hook not in _POST_SWAP_HOOKS:
        _POST_SWAP_HOOKS.append(hook)


def _fire_post_swap_hooks(record: BundleRecord) -> tuple[ExtensionError, ...]:
    """Fire every post-swap hook; return one warning per hook that raised.

    Hook failures must not roll back the swap (the registry mutation is
    already committed) and must not abort iteration over remaining hooks,
    but they are surfaced as warnings on :class:`ReloadResult` so the
    HTTP response can carry a "swap succeeded but cache rebuild failed"
    signal instead of silently returning 200 OK with empty deltas.
    """
    warnings: list[ExtensionError] = []
    for hook in _POST_SWAP_HOOKS:
        try:
            hook(record)
        except Exception as exc:
            # A failing hook (cache rebuild error, etc.) must not roll back
            # the swap or block the next hook.  Log and record the failure
            # so the caller can attach it to ReloadResult.warnings.
            logger.exception("post-swap reload hook %r failed for bundle %r", hook, record.bundle)
            warnings.append(
                ExtensionError(
                    code="reload-post-swap-hook-failed",
                    message=(
                        f"Post-swap hook {getattr(hook, '__qualname__', repr(hook))} "
                        f"raised for bundle {record.bundle!r}: {exc!r}"
                    ),
                    location=record.bundle,
                    content=record.bundle,
                    hint=(
                        "The bundle swap committed but a post-swap side-effect "
                        "(e.g. component cache rebuild) failed.  Check server logs "
                        "at WARNING/ERROR level; a full server restart may be needed "
                        "to recover the palette."
                    ),
                )
            )
    return tuple(warnings)


# ---------------------------------------------------------------------------
# ReloadResult
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReloadResult:
    """Outcome of a single :func:`reload_bundle` call.

    On success: ``ok`` is True, ``record`` is the freshly-installed
    :class:`BundleRecord`, ``components_added`` and ``components_removed``
    list class names that changed.

    On failure: ``ok`` is False, ``errors`` carries one or more typed
    :class:`ExtensionError` instances.  ``record`` is the *previous*
    record (still live and unchanged), or ``None`` if no record existed
    and the reload was a fresh install attempt that failed.
    """

    ok: bool
    bundle: str
    errors: tuple[ExtensionError, ...] = ()
    warnings: tuple[ExtensionError, ...] = ()
    record: BundleRecord | None = None
    components_added: tuple[str, ...] = ()
    components_removed: tuple[str, ...] = ()
    reload_id: str = ""

    def to_dict(self) -> dict[str, object]:
        """Serializable representation for HTTP bodies / CLI JSON output."""
        return {
            "ok": self.ok,
            "bundle": self.bundle,
            "reload_id": self.reload_id,
            "components_added": list(self.components_added),
            "components_removed": list(self.components_removed),
            "errors": [e.to_dict() for e in self.errors],
            "warnings": [w.to_dict() for w in self.warnings],
        }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def reload_bundle(
    registry: BundleRegistry,
    bundle: str,
    *,
    source_path: Path | str | None = None,
    slot: Literal["official", "extra"] | None = None,
) -> ReloadResult:
    """Reload one Bundle into ``registry`` via the five-stage atomic swap.

    Args:
        registry: The live :class:`BundleRegistry` to mutate.  Pass the
            process default registry from ``get_default_registry()`` for
            production use; tests should construct their own.
        bundle: Snake-case bundle name to reload.  Must already be
            registered, OR ``source_path`` must be supplied for a fresh
            install via reload (the latter is what
            ``extension reload --all`` uses on first run).
        source_path: Path to the extension root (containing the manifest)
            for an @official-slot reload, or to the bundle directory
            itself for an @extra-slot reload.  Defaults to whatever path
            the existing :class:`BundleRecord` was loaded from.
        slot: Which slot to load into.  Defaults to the existing record's
            slot, or ``official`` for a fresh install.

    Raises:
        :class:`ReloadInProgressError` -- a second reload for the same
        Bundle is requested while the first is still running.  Caller
        should translate this into a typed ``reload-in-progress`` API
        response.

    Returns:
        :class:`ReloadResult` with success/failure status and the
        components_added / components_removed deltas.
    """
    reload_id = uuid.uuid4().hex
    live = registry.get_bundle(bundle)

    # Resolve effective source + slot from the live record when not given.
    effective_source = _resolve_source(source_path, live)
    effective_slot: Literal["official", "extra"] = slot or (live.slot if live else SLOT_OFFICIAL)

    # No source path AND no live record -> we cannot proceed.
    if effective_source is None and live is None:
        return _failure(
            bundle=bundle,
            reload_id=reload_id,
            errors=[
                ExtensionError(
                    code="reload-bundle-not-installed",
                    message=f"Bundle {bundle!r} is not registered and no source path was supplied.",
                    location=bundle,
                    content=bundle,
                    hint=(
                        "Install the extension first (pip install / seed directory / "
                        "`lfx extension dev <path>`), then reload via "
                        "`lfx extension reload <extension-id> --bundle <name>`."
                    ),
                )
            ],
            previous=None,
        )

    # If we have a source path but it doesn't exist, fail before touching
    # the registry's reload-in-progress flag so a typo doesn't lock out
    # legitimate reloads.
    if effective_source is not None and not effective_source.is_dir():
        return _failure(
            bundle=bundle,
            reload_id=reload_id,
            errors=[
                ExtensionError(
                    code="reload-source-missing",
                    message=f"Source path {effective_source} for bundle {bundle!r} does not exist.",
                    location=bundle,
                    content=str(effective_source),
                    hint=(
                        "Confirm the extension is still installed at this path; "
                        "if not, uninstall the bundle from the registry instead of reloading."
                    ),
                )
            ],
            previous=live,
        )

    # Acquire the per-bundle reload-in-progress guard.  Re-raises
    # ReloadInProgressError to the caller.
    with registry.reload_in_progress(bundle):
        return _run_pipeline(
            registry=registry,
            bundle=bundle,
            effective_source=effective_source,
            effective_slot=effective_slot,
            reload_id=reload_id,
            previous=live,
        )


# ---------------------------------------------------------------------------
# Pipeline body (called under the reload-in-progress guard)
# ---------------------------------------------------------------------------


def _run_pipeline(
    *,
    registry: BundleRegistry,
    bundle: str,
    effective_source: Path | None,
    effective_slot: Literal["official", "extra"],
    reload_id: str,
    previous: BundleRecord | None,
) -> ReloadResult:
    """Run Stages 1-5 with the in-progress guard already held."""
    staging_namespace = f"__reload_staging__.{reload_id}"
    try:
        return _run_pipeline_body(
            registry=registry,
            bundle=bundle,
            effective_source=effective_source,
            effective_slot=effective_slot,
            reload_id=reload_id,
            previous=previous,
            staging_namespace=staging_namespace,
        )
    finally:
        # Belt-and-braces: every controlled return path already drops the
        # staging namespace, but if anything raises (a loader bug, an OOM
        # mid-import, KeyboardInterrupt) we still purge sys.modules so the
        # next reload of this bundle starts from a clean slate instead of
        # tripping over orphaned ``__reload_staging__.<id>.*`` entries.
        # _drop_staging_modules is idempotent; calling it twice is cheap.
        _drop_staging_modules(staging_namespace)


def _run_pipeline_body(
    *,
    registry: BundleRegistry,
    bundle: str,
    effective_source: Path | None,
    effective_slot: Literal["official", "extra"],
    reload_id: str,
    previous: BundleRecord | None,
    staging_namespace: str,
) -> ReloadResult:
    """Pipeline body wrapped by :func:`_run_pipeline` for guaranteed cleanup."""
    # ---------- Stage 1: parallel load into staging namespace ----------
    if effective_source is None:
        # Should not happen: caller checked.  Defensive.
        return _failure(
            bundle=bundle,
            reload_id=reload_id,
            errors=[
                ExtensionError(
                    code="reload-bundle-not-installed",
                    message=f"Bundle {bundle!r} has no source path to reload from.",
                    location=bundle,
                    content=bundle,
                    hint="Re-install the extension to record its source path.",
                )
            ],
            previous=previous,
        )

    # @extra inline bundles record source_path as the bundle directory
    # itself (no manifest at that level), so load_extension() would
    # respond with manifest-not-found.  Route those through the inline
    # loader, which derives identity from the directory name + optional
    # bundle.json the same way startup discovery does.
    #
    # Log the resolved source before the load so a "200 OK with empty
    # deltas" repro can be triaged from the server log alone: if the
    # path here is not the path the operator was editing, the bug is
    # cross-source bundle-name shadowing in the registry-population
    # pass, not the loader itself.  Logged at INFO so it shows up under
    # the default langflow verbosity.
    logger.info(
        "extension.reload.stage1_load",
        extra={
            "event": "reload_stage1_load",
            "bundle": bundle,
            "slot": effective_slot,
            "source_path": str(effective_source),
            "reload_id": reload_id,
            "staging_namespace": staging_namespace,
        },
    )
    if effective_slot == SLOT_EXTRA:
        staging: LoadResult = load_inline_bundle(
            effective_source,
            module_namespace=staging_namespace,
        )
    else:
        staging = load_extension(
            effective_source,
            slot=effective_slot,
            module_namespace=staging_namespace,
        )

    # ---------- Stage 2: validate ----------
    if not staging.ok:
        _drop_staging_modules(staging_namespace)
        result = _failure(
            bundle=bundle,
            reload_id=reload_id,
            errors=tuple(staging.errors),
            warnings=tuple(staging.warnings),
            previous=previous,
        )
        _emit_bundle_reload_event(result)
        return result

    if staging.bundle != bundle:
        _drop_staging_modules(staging_namespace)
        result = _failure(
            bundle=bundle,
            reload_id=reload_id,
            errors=(
                ExtensionError(
                    code="reload-bundle-name-mismatch",
                    message=(
                        f"Reload source declares bundle {staging.bundle!r} but the registered name is {bundle!r}."
                    ),
                    location=str(effective_source),
                    content=staging.bundle or "<unknown>",
                    hint=(
                        "The manifest at this path does not name the bundle being "
                        "reloaded.  Pass --bundle to disambiguate or restore the "
                        "manifest to its original name."
                    ),
                ),
            ),
            previous=previous,
        )
        _emit_bundle_reload_event(result)
        return result

    # ---------- Stage 3: atomic swap under the registry write lock ----------
    # Build the production-namespace component records before swapping.  We do
    # not yet touch sys.modules; the registry mutation itself is the atomic
    # commit point.  Renaming sys.modules entries happens *under* the same
    # write lock so that any concurrent path looking at sys.modules sees a
    # state consistent with the registry it just snapshotted.
    new_components = tuple(_retag_component(c, staging_namespace, DEFAULT_MODULE_NAMESPACE) for c in staging.components)
    new_record = BundleRecord(
        bundle=bundle,
        extension_id=staging.extension_id or (previous.extension_id if previous else bundle),
        extension_version=staging.extension_version or (previous.extension_version if previous else "0.0.0"),
        slot=effective_slot,
        components=new_components,
        distribution=staging.distribution,
        source_path=effective_source,
    )

    # Atomic swap: hold the registry write lock across BOTH the sys.modules
    # rename and the BundleRecord install so concurrent readers can never
    # observe new modules with the old record (or vice versa).  The lock is
    # an RLock, so install_bundle()'s own internal acquire is a no-op
    # reentry while this context is active.
    with registry.write_locked():
        _swap_sys_modules(
            previous=previous,
            new_components=new_components,
            staging_components=staging.components,
        )
        registry.install_bundle(new_record)

    # ---------- Stage 4: cleanup leftover staging entries ----------
    _drop_staging_modules(staging_namespace)

    # Fire post-swap hooks (component cache rebuild, etc.) BEFORE we emit
    # the result so callers blocking on the HTTP response see a consistent
    # registry + cache state.  Hook failures do not roll back the swap,
    # but are surfaced on ReloadResult.warnings so the API caller can
    # detect "swap committed but cache rebuild broke".
    hook_warnings = _fire_post_swap_hooks(new_record)

    # ---------- Stage 5: emit bundle_reloaded ----------
    added, removed = _diff(previous, new_record)
    result = ReloadResult(
        ok=True,
        bundle=bundle,
        record=new_record,
        components_added=added,
        components_removed=removed,
        warnings=tuple(staging.warnings) + hook_warnings,
        reload_id=reload_id,
    )
    _emit_bundle_reload_event(result)
    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_source(source_path: Path | str | None, live: BundleRecord | None) -> Path | None:
    """Pick the effective source path, preferring the explicit argument."""
    if source_path is not None:
        return Path(source_path).resolve()
    if live is not None and live.source_path is not None:
        return Path(live.source_path).resolve()
    return None


def _retag_component(
    component: LoadedComponent,
    staging_namespace: str,
    target_namespace: str,
) -> LoadedComponent:
    """Return a copy of ``component`` with its module_name re-prefixed.

    The loader stamped the staging namespace on every component during
    Stage 1; Stage 3 swaps it back to the production namespace so the
    registry's class metadata matches where the module ultimately lives
    in ``sys.modules``.

    Raises :class:`AssertionError` if the loader didn't honour the
    ``module_namespace=staging_namespace`` contract for this component.
    Silently returning the unmodified component (the prior behaviour)
    would let :func:`_swap_sys_modules` succeed against the wrong
    sys.modules entries, leaving the BundleRecord pointing at modules
    under an unexpected prefix.
    """
    old_prefix = f"{staging_namespace}."
    if not component.module_name.startswith(old_prefix):
        msg = (
            f"loader returned component {component.class_name!r} with "
            f"module_name={component.module_name!r}, which does not start "
            f"with the staging prefix {old_prefix!r}; the staging-namespace "
            "contract is broken upstream of reload."
        )
        raise AssertionError(msg)
    new_module_name = f"{target_namespace}.{component.module_name[len(old_prefix) :]}"
    return replace(component, module_name=new_module_name)


def _swap_sys_modules(
    *,
    previous: BundleRecord | None,
    new_components: Iterable[LoadedComponent],
    staging_components: Iterable[LoadedComponent],
) -> None:
    """Drop old prod entries; rename staging entries to their prod names.

    Held under the registry write lock by virtue of being called from
    :func:`_run_pipeline` between :func:`install_bundle` and stage-4
    cleanup.  Ordering: drop-old first so a prod-name reuse picks up the
    new module, not a stale one.

    Module ``__name__`` attributes are also rewritten so ``inspect`` /
    pickling treat the module as living at its production name.  Each
    component class's ``__module__`` is retagged in lockstep so
    ``inspect.getmodule(cls)`` resolves against ``sys.modules`` under the
    production name; without this, post-swap consumers (notably
    :func:`Component.set_class_code`) see ``cls.__module__`` pointing at
    a staging key that has just been dropped and silently fail.
    """
    # Materialize the iterables so we can walk them twice (once to build
    # the rename map, once to retag each class's __module__).
    staging_list: list[LoadedComponent] = list(staging_components)
    new_list: list[LoadedComponent] = list(new_components)

    if previous is not None:
        for old in previous.components:
            sys.modules.pop(old.module_name, None)

    # Map staging name -> new prod name for the swap.
    rename_map: dict[str, str] = {
        staged.module_name: new.module_name for staged, new in zip(staging_list, new_list, strict=True)
    }

    for staging_name, prod_name in rename_map.items():
        module = sys.modules.pop(staging_name, None)
        if module is None:
            continue
        # __name__ is a normal string attr on regular modules; only
        # pathological subclasses block writes.  Best-effort.
        with contextlib.suppress(AttributeError, TypeError):
            module.__name__ = prod_name
        sys.modules[prod_name] = module

    # Retag each component class's __module__ to the production name.
    # The class was defined while its module was registered under the
    # staging namespace, so cls.__module__ was stamped at class-definition
    # time to "__reload_staging__.<reload_id>....".  Renaming the
    # sys.modules entry above does not propagate to the class objects.
    # Without this fixup, inspect.getmodule(cls) returns None (the
    # staging key has been dropped from sys.modules) and downstream
    # consumers like Component.set_class_code raise -- silently breaking
    # the post-swap cache rebuild (the empty-palette-after-reload bug).
    for new in new_list:
        with contextlib.suppress(AttributeError, TypeError):
            new.klass.__module__ = new.module_name


def _drop_staging_modules(staging_namespace: str) -> None:
    """Remove any remaining ``<staging_namespace>.*`` entries from sys.modules.

    Stage 4 cleanup.  Tolerates the staging namespace being already empty
    (the happy path swapped everything to prod names in Stage 3).
    """
    prefix = f"{staging_namespace}."
    stale = [name for name in sys.modules if name == staging_namespace or name.startswith(prefix)]
    for name in stale:
        sys.modules.pop(name, None)


def _diff(
    previous: BundleRecord | None,
    new_record: BundleRecord,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return (added, removed) class-name tuples, each sorted lexicographically."""
    new_names = new_record.class_names
    old_names = previous.class_names if previous is not None else frozenset()
    added = tuple(sorted(new_names - old_names))
    removed = tuple(sorted(old_names - new_names))
    return added, removed


def _failure(
    *,
    bundle: str,
    reload_id: str,
    errors: Iterable[ExtensionError],
    warnings: Iterable[ExtensionError] = (),
    previous: BundleRecord | None,
) -> ReloadResult:
    """Build a failure ReloadResult that leaves ``previous`` as the live record."""
    return ReloadResult(
        ok=False,
        bundle=bundle,
        errors=tuple(errors),
        warnings=tuple(warnings),
        record=previous,
        reload_id=reload_id,
    )


# ---------------------------------------------------------------------------
# Event emission (Stage 5)
# ---------------------------------------------------------------------------


# TODO(LE-1017): replace this stub with a call to
# ExtensionEventsService.emit(...) once the events pipeline ticket lands.
# The shape of the payload below is what the events service will consume:
# the ReloadResult is serializable and carries everything needed for the
# bundle_reloaded / bundle_reload_failed discriminants.
def _emit_bundle_reload_event(result: ReloadResult) -> None:
    """Stub for the LE-1017 events pipeline.

    Currently logs a structured event; LE-1017 will swap the body to
    ``ExtensionEventsService.emit("bundle_reloaded" | "bundle_reload_failed", payload)``.
    Tests can monkey-patch this symbol to capture emissions without
    waiting for the events service to land.
    """
    if result.ok:
        logger.info(
            "extension.bundle_reloaded",
            extra={
                "event": "bundle_reloaded",
                "bundle": result.bundle,
                "reload_id": result.reload_id,
                "components_added": list(result.components_added),
                "components_removed": list(result.components_removed),
            },
        )
    else:
        logger.warning(
            "extension.bundle_reload_failed",
            extra={
                "event": "bundle_reload_failed",
                "bundle": result.bundle,
                "reload_id": result.reload_id,
                "errors": [e.to_dict() for e in result.errors],
            },
        )


# Re-export for caller convenience.
__all__ = [
    "ReloadInProgressError",
    "ReloadResult",
    "reload_bundle",
]

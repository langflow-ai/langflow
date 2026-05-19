"""``sys.modules`` surgery primitives extracted from reload.py.

Why this lives in its own module:
    The reload pipeline file got large (single-responsibility creep) and
    the two primitives below are a cohesive, separately-testable unit:
    ``_swap_sys_modules`` is the only function in the whole subsystem
    that mutates the live ``_lfx_ext.*`` namespace, and
    ``_drop_staging_modules`` is its inverse-cleanup pair.  Keeping them
    in their own file makes them easy to audit (the security-relevant
    half of reload) and tests can target them in isolation.

These functions must be called from inside a registry write lock; see
:func:`lfx.extension.reload.reload_bundle` for the surrounding pipeline.
"""

from __future__ import annotations

import contextlib
import logging
import sys
from dataclasses import replace
from typing import TYPE_CHECKING

from lfx.extension.errors import ExtensionError

if TYPE_CHECKING:
    from collections.abc import Iterable

    from lfx.extension.bundle_registry import BundleRecord
    from lfx.extension.loader import LoadedComponent

logger = logging.getLogger(__name__)


def retag_component(
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
    would let :func:`swap_sys_modules` succeed against the wrong
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


def swap_sys_modules(
    *,
    previous: BundleRecord | None,
    new_components: Iterable[LoadedComponent],
    staging_components: Iterable[LoadedComponent],
) -> list[ExtensionError]:
    """Drop old prod entries; rename staging entries to their prod names.

    Held under the registry write lock by virtue of being called from
    the reload pipeline between ``install_bundle`` and the stage-4
    cleanup.

    Returns a list of warnings.  An empty list means the swap installed
    every staging module and retagged every class cleanly.  A non-empty
    list flags the load-bearing ``cls.__module__`` retag failures so the
    caller can surface them on :attr:`ReloadResult.warnings` instead of
    silently regressing the empty-palette-after-reload bug.

    Rollback safety
    ---------------
    Every ``sys.modules`` key the swap may touch -- staging names, the
    new prod names, and the previous-record prod names being evicted --
    is snapshotted *before* any mutation, together with
    ``module.__name__`` for each staging module that will be renamed
    in place.  If ``BaseException`` (including ``KeyboardInterrupt`` /
    ``SystemExit`` / ``MemoryError``) is raised partway through the
    rename loop, the ``except`` clause restores ``sys.modules`` to its
    byte-identical pre-call state and reverts the ``module.__name__``
    mutations.  A partially-completed rename window therefore cannot
    leave the prod namespace half-swapped (e.g. with the new staging
    module bound at the prod name while the old prod module is silently
    dropped).

    The pre-mutation length-mismatch tripwire (``zip(strict=True)``)
    re-raises as ``AssertionError`` *before* any snapshot is built --
    that path is a no-op rollback by construction.
    """
    staging_list: list[LoadedComponent] = list(staging_components)
    new_list: list[LoadedComponent] = list(new_components)
    warnings: list[ExtensionError] = []

    try:
        rename_map: dict[str, str] = {
            staged.module_name: new.module_name for staged, new in zip(staging_list, new_list, strict=True)
        }
    except ValueError as exc:
        # Length-mismatch invariant tripwire.  The loader contract
        # guarantees staging_components and new_components are 1:1; if
        # this ever fires, upstream retag_component dropped or
        # duplicated an entry.  Surface a loud assertion and leave
        # sys.modules untouched -- the previous record stays live.
        msg = f"reload swap invariant broken: {exc}"
        raise AssertionError(msg) from exc

    # Snapshot every key the swap may touch, plus the staging modules'
    # original ``__name__`` attributes.  ``_absent`` distinguishes
    # "key missing pre-call" from "key present with value ``None``"
    # (sys.modules legitimately uses ``None`` as a negative-import
    # cache marker).  Built BEFORE the mutation try-block so a failure
    # during snapshot construction leaves sys.modules untouched.
    _absent: object = object()
    touched_keys: set[str] = set(rename_map.keys()) | set(rename_map.values())
    if previous is not None:
        touched_keys.update(old.module_name for old in previous.components)
    sys_modules_snapshot: dict[str, object] = {key: sys.modules.get(key, _absent) for key in touched_keys}
    staging_name_snapshot: dict[str, str] = {}
    for staging_name in rename_map:
        module = sys.modules.get(staging_name)
        if module is None:
            continue
        # A module without ``__name__`` cannot be retagged anyway; the
        # rename loop's ``contextlib.suppress`` will absorb the write
        # attempt, so we have nothing to revert here.
        with contextlib.suppress(AttributeError):
            staging_name_snapshot[staging_name] = module.__name__

    try:
        if previous is not None:
            for old in previous.components:
                sys.modules.pop(old.module_name, None)

        for staging_name, prod_name in rename_map.items():
            module = sys.modules.pop(staging_name, None)
            if module is None:
                continue
            with contextlib.suppress(AttributeError, TypeError):
                module.__name__ = prod_name
            sys.modules[prod_name] = module
    except BaseException:
        # Byte-restore: every touched key returns to its pre-call value
        # (or is popped if it was absent).  Unconditional assignment --
        # ``setdefault`` would leave prod names that the rename loop
        # already overwrote pointing at the new staging module.
        for key, value in sys_modules_snapshot.items():
            if value is _absent:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = value  # type: ignore[assignment]
        # Revert any in-place ``__name__`` mutations on staging modules
        # the rename loop reached before the interrupt fired.  Without
        # this the staging modules survive (restored above) but carry
        # the prod-namespace ``__name__`` attribute, which would mislead
        # ``inspect.getmodule`` and subsequent retag attempts.  The
        # equality guard skips the ``__setattr__`` call when the rename
        # loop never actually mutated ``__name__`` (the interrupt fired
        # before the assignment landed) -- important both to avoid
        # spurious writes and to avoid re-triggering a ``__setattr__``
        # hook that may have raised the original exception.
        for staging_name, original_name in staging_name_snapshot.items():
            module = sys.modules.get(staging_name)
            if module is None:
                continue
            try:
                current_name = module.__name__
            except AttributeError:
                continue
            if current_name == original_name:
                continue
            with contextlib.suppress(AttributeError, TypeError):
                module.__name__ = original_name
        raise

    for new in new_list:
        try:
            new.klass.__module__ = new.module_name
        except (AttributeError, TypeError) as exc:
            logger.warning(
                "reload: could not retag %s.__module__ to %r (%s); "
                "inspect.getmodule will fall through and the post-swap cache "
                "rebuild may produce an empty palette for this class.",
                new.class_name,
                new.module_name,
                exc,
            )
            warnings.append(
                ExtensionError(
                    code="reload-class-retag-failed",
                    message=(
                        f"Could not retag {new.class_name}.__module__ to "
                        f"{new.module_name!r}: {exc!r}. "
                        "The post-swap cache rebuild may produce an empty palette for this class."
                    ),
                    location=new.module_name,
                    content=new.class_name,
                    hint=(
                        "A pathological metaclass or read-only __module__ descriptor "
                        "blocked the retag; the component class will not survive a hot reload cleanly."
                    ),
                )
            )
    return warnings


def drop_staging_modules(staging_namespace: str) -> None:
    """Remove any remaining ``<staging_namespace>.*`` entries from sys.modules.

    Stage 4 cleanup.  Tolerates the staging namespace being already empty
    (the happy path swapped everything to prod names in Stage 3).
    """
    prefix = f"{staging_namespace}."
    stale = [name for name in sys.modules if name == staging_namespace or name.startswith(prefix)]
    for name in stale:
        sys.modules.pop(name, None)

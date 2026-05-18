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

    Non-destructive ordering invariant: the rename map is built BEFORE
    any sys.modules mutation, and the old modules are snapshotted before
    being popped so a length-mismatch in zip(..., strict=True) can be
    rolled back into a no-op rather than leaving the prod namespace
    permanently shredded.
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

    recovery: dict[str, object] = {}
    try:
        if previous is not None:
            for old in previous.components:
                module = sys.modules.pop(old.module_name, None)
                if module is not None:
                    recovery[old.module_name] = module

        for staging_name, prod_name in rename_map.items():
            module = sys.modules.pop(staging_name, None)
            if module is None:
                continue
            with contextlib.suppress(AttributeError, TypeError):
                module.__name__ = prod_name
            sys.modules[prod_name] = module
    except BaseException:
        for name, module in recovery.items():
            sys.modules.setdefault(name, module)  # type: ignore[arg-type]
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

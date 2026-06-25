"""Lazy, low-overhead auto-apply hook.

The package is auto-imported at interpreter startup (via a ``.pth`` line). We do
NOT want to import the (heavy) lfx package on every ``python`` invocation in the
environment, so instead of applying eagerly we install a ``sys.meta_path``
finder that triggers :func:`langflow_extra_providers.patch.apply` exactly once,
right after Langflow imports its model-catalog module.

If lfx's model catalog is already imported when we load (e.g. someone imported
us late), we apply immediately.
"""

from __future__ import annotations

import importlib.abc
import importlib.util
import logging
import sys

logger = logging.getLogger("langflow_extra_providers")

# Importing this module finalizes the provider registration, so it is the right
# trigger point: by the time it finishes executing, MODEL_PROVIDER_METADATA and
# _STATIC_MODELS_DETAILED exist and are safe to mutate.
_TRIGGER_MODULE = "lfx.base.models.unified_models.provider_queries"


def _run_apply() -> None:
    try:
        from .patch import apply

        apply()
    except Exception:  # noqa: BLE001 - never break a host process on our account
        logger.exception("langflow-extra-providers: auto-apply failed")


class _ApplyOnImportFinder(importlib.abc.MetaPathFinder):
    """Fires :func:`_run_apply` after the trigger module is executed, once."""

    def __init__(self) -> None:
        self._fired = False

    def find_spec(self, fullname, path=None, target=None):  # noqa: ARG002
        if self._fired or fullname != _TRIGGER_MODULE:
            return None
        # Resolve the real spec without re-entering ourselves.
        try:
            sys.meta_path.remove(self)
        except ValueError:
            return None
        try:
            spec = importlib.util.find_spec(fullname)
        except Exception:  # noqa: BLE001
            return None
        if spec is None or spec.loader is None:
            return None

        loader = spec.loader
        real_exec_module = loader.exec_module

        def exec_module(module, _real=real_exec_module):
            _real(module)
            # Guard against double-fire; this finder is already detached.
            if not self._fired:
                self._fired = True
                _run_apply()

        # Patching this spec's own loader instance is safe — FileFinder hands
        # out a fresh loader per module.
        loader.exec_module = exec_module  # type: ignore[method-assign]
        return spec


def install() -> None:
    """Apply now if the catalog is already loaded, else arm the import hook."""
    if _TRIGGER_MODULE in sys.modules:
        _run_apply()
        return
    # Avoid installing twice.
    if any(isinstance(f, _ApplyOnImportFinder) for f in sys.meta_path):
        return
    sys.meta_path.insert(0, _ApplyOnImportFinder())

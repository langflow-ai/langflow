# lfx-bundles-shim
"""Compatibility shim: lfx.components.azure moved to lfx-azure.

This module re-points to the installed bundle distribution. It contains
no component implementations and no third-party dependencies, and is
removed once the deprecation window closes (M4).
"""

import importlib
import sys

try:
    sys.modules[__name__] = importlib.import_module("lfx_azure.components.azure")
except ModuleNotFoundError as exc:
    if exc.name is not None and (exc.name == "lfx_azure" or exc.name.startswith("lfx_azure.")):
        msg = (
            "The 'azure' components moved to the 'lfx-azure' distribution. "
            "Install it with: pip install lfx-azure (or pip install langflow, which includes it)."
        )
        raise ModuleNotFoundError(msg, name="lfx_azure") from exc
    raise

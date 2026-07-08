# lfx-bundles-shim
"""Compatibility shim: lfx.components.exa moved to the lfx-exa bundle.

This module re-points to the installed bundle distribution. It contains
no component implementations and no third-party dependencies, and is
removed once the deprecation window closes (M4).
"""

import importlib
import sys

try:
    sys.modules[__name__] = importlib.import_module("lfx_exa.components.exa")
except ModuleNotFoundError as exc:
    if exc.name is not None and (exc.name == "lfx_exa" or exc.name.startswith("lfx_exa.")):
        msg = (
            "The 'exa' components moved to the 'lfx-exa' distribution. "
            "Install it with:  pip install lfx-exa   "
            "(or 'pip install langflow', which bundles it)."
        )
        raise ModuleNotFoundError(msg, name="lfx_exa") from exc
    raise

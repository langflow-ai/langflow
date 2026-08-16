# lfx-bundles-shim
"""Compatibility shim: lfx.components.google moved to lfx-google.

This module re-points to the installed bundle distribution. It contains
no component implementations and no third-party dependencies, and is
removed once the deprecation window closes (M4).
"""

import importlib
import sys

try:
    sys.modules[__name__] = importlib.import_module("lfx_google.components.google")
except ModuleNotFoundError as exc:
    if exc.name is not None and (exc.name == "lfx_google" or exc.name.startswith("lfx_google.")):
        msg = (
            "The 'google' components moved to the 'lfx-google' distribution. "
            "Install it with: pip install lfx-google (or pip install langflow, which includes it)."
        )
        raise ModuleNotFoundError(msg, name="lfx_google") from exc
    raise

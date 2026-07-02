# lfx-bundles-shim
"""Compatibility shim: lfx.components.git moved to lfx-bundles.

This module re-points to the installed bundle distribution. It contains
no component implementations and no third-party dependencies, and is
removed once the deprecation window closes (M4).
"""

import importlib
import sys

try:
    sys.modules[__name__] = importlib.import_module("lfx_bundles.git")
except ModuleNotFoundError as exc:
    if exc.name is not None and (exc.name == "lfx_bundles" or exc.name.startswith("lfx_bundles.")):
        msg = "The 'git' components moved to the 'lfx-bundles' distribution. Install it with:  pip install lfx-bundles."
        raise ModuleNotFoundError(msg, name="lfx_bundles") from exc
    raise

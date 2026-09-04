# lfx-bundles-shim
"""Compatibility shim: lfx.components.amazon moved to the lfx-amazon bundle.

This module re-points to the installed bundle distribution. It contains
no component implementations and no third-party dependencies, and is
removed once the deprecation window closes (M4).
"""

import importlib
import sys

try:
    sys.modules[__name__] = importlib.import_module("lfx_amazon.components.amazon")
except ModuleNotFoundError as exc:
    if exc.name is not None and (exc.name == "lfx_amazon" or exc.name.startswith("lfx_amazon.")):
        msg = (
            "The 'amazon' components moved to the 'lfx-amazon' distribution. "
            "Install it with:  pip install lfx-amazon   "
            "(or 'pip install langflow', which bundles it)."
        )
        raise ModuleNotFoundError(msg, name="lfx_amazon") from exc
    raise

# lfx-bundles-shim
"""Compatibility shim: lfx.components.cohere moved to the lfx-cohere bundle.

This module re-points to the installed bundle distribution. It contains
no component implementations and no third-party dependencies, and is
removed once the deprecation window closes (M4).
"""

import importlib
import sys

try:
    sys.modules[__name__] = importlib.import_module("lfx_cohere.components.cohere")
except ModuleNotFoundError as exc:
    if exc.name is not None and (exc.name == "lfx_cohere" or exc.name.startswith("lfx_cohere.")):
        msg = (
            "The 'cohere' components moved to the 'lfx-cohere' distribution. "
            "Install it with:  pip install lfx-cohere   "
            "(or 'pip install langflow', which bundles it)."
        )
        raise ModuleNotFoundError(msg, name="lfx_cohere") from exc
    raise

# lfx-bundles-shim
"""Compatibility shim: lfx.components.anthropic moved to the lfx-anthropic bundle.

This module re-points to the installed bundle distribution. It contains
no component implementations and no third-party dependencies, and is
removed once the deprecation window closes (M4).
"""

import importlib
import sys

try:
    sys.modules[__name__] = importlib.import_module("lfx_anthropic.components.anthropic")
except ModuleNotFoundError as exc:
    if exc.name is not None and (exc.name == "lfx_anthropic" or exc.name.startswith("lfx_anthropic.")):
        msg = (
            "The 'anthropic' components moved to the 'lfx-anthropic' distribution. "
            "Install it with:  pip install lfx-anthropic   "
            "(or 'pip install langflow', which bundles it)."
        )
        raise ModuleNotFoundError(msg, name="lfx_anthropic") from exc
    raise

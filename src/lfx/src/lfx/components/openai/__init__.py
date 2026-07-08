# lfx-bundles-shim
"""Compatibility shim: lfx.components.openai moved to the lfx-openai bundle.

This module re-points to the installed bundle distribution. It contains
no component implementations and no third-party dependencies, and is
removed once the deprecation window closes (M4).
"""

import importlib
import sys

try:
    sys.modules[__name__] = importlib.import_module("lfx_openai.components.openai")
except ModuleNotFoundError as exc:
    if exc.name is not None and (exc.name == "lfx_openai" or exc.name.startswith("lfx_openai.")):
        msg = (
            "The 'openai' components moved to the 'lfx-openai' distribution. "
            "Install it with:  pip install lfx-openai   "
            "(or 'pip install langflow', which bundles it)."
        )
        raise ModuleNotFoundError(msg, name="lfx_openai") from exc
    raise

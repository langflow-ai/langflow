# lfx-bundles-shim
"""Compatibility shim: lfx.components.ollama moved to lfx-ollama.

This module re-points to the installed bundle distribution. It contains
no component implementations and no third-party dependencies, and is
removed once the deprecation window closes (M4).
"""

import importlib
import sys

try:
    sys.modules[__name__] = importlib.import_module("lfx_ollama.components.ollama")
except ModuleNotFoundError as exc:
    if exc.name is not None and (exc.name == "lfx_ollama" or exc.name.startswith("lfx_ollama.")):
        msg = (
            "The 'ollama' components moved to the 'lfx-ollama' distribution. "
            "Install it with: pip install lfx-ollama (or pip install langflow, which includes it)."
        )
        raise ModuleNotFoundError(msg, name="lfx_ollama") from exc
    raise

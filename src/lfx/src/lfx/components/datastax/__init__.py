# lfx-bundles-shim
"""Compatibility shim: lfx.components.datastax moved to the lfx-datastax bundle.

This module re-points to the installed bundle distribution. It contains
no component implementations and no third-party dependencies, and is
removed once the deprecation window closes (M4).
"""

import importlib
import sys

try:
    sys.modules[__name__] = importlib.import_module("lfx_datastax.components.datastax")
except ModuleNotFoundError as exc:
    if exc.name is not None and (exc.name == "lfx_datastax" or exc.name.startswith("lfx_datastax.")):
        msg = (
            "The 'datastax' components moved to the 'lfx-datastax' distribution. "
            "Install it with:  pip install lfx-datastax   "
            "(or 'pip install langflow', which bundles it)."
        )
        raise ModuleNotFoundError(msg, name="lfx_datastax") from exc
    raise

# lfx-bundles-shim
"""Compatibility shim: lfx.base.datastax moved to the lfx-datastax bundle.

This module re-points to ``lfx_datastax.base`` in the installed bundle
distribution. It exists because component code stored inside saved flows
(and the starter-project templates) imports
``lfx.base.datastax.astradb_base`` directly, and that stored source is
re-executed verbatim at flow build time -- so the legacy path must keep
resolving. It contains no implementations and no third-party
dependencies, and is removed once the deprecation window closes (M4).
"""

import importlib
import sys

try:
    sys.modules[__name__] = importlib.import_module("lfx_datastax.base")
except ModuleNotFoundError as exc:
    if exc.name is not None and (exc.name == "lfx_datastax" or exc.name.startswith("lfx_datastax.")):
        msg = (
            "The 'datastax' base utilities moved to the 'lfx-datastax' distribution. "
            "Install it with:  pip install lfx-datastax   "
            "(or 'pip install langflow', which bundles it)."
        )
        raise ModuleNotFoundError(msg, name="lfx_datastax") from exc
    raise

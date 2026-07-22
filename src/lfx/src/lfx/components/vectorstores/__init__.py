# lfx-bundles-shim
"""Compatibility shim: lfx.components.vectorstores moved to lfx-bundles.

The lone LocalDBComponent is Chroma-backed, so it lives in the ``chroma``
bundle (this is a cross-bundle shim: the dir is ``vectorstores`` but the
target bundle is ``chroma``). It contains no component implementations and no
third-party dependencies, and is removed once the deprecation window closes (M4).
"""

import importlib
import sys

try:
    sys.modules[__name__] = importlib.import_module("lfx_bundles.chroma")
except ModuleNotFoundError as exc:
    if exc.name is not None and (exc.name == "lfx_bundles" or exc.name.startswith("lfx_bundles.")):
        msg = (
            "The 'vectorstores' components moved to the 'lfx-bundles' distribution. "
            "Install it with: pip install lfx-bundles."
        )
        raise ModuleNotFoundError(msg, name="lfx_bundles") from exc
    raise

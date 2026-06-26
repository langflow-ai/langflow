# lfx-bundles-shim
"""Compatibility shim: lfx.components.spider re-points to lfx-bundles.

The SpiderTool component lives in the ``lfx-bundles`` distribution; this module
aliases the old in-tree import path to it and ships no implementation and no
third-party dependency.  It exists so legacy ``lfx.components.spider`` imports
resolve and the i18n string extractor (which walks ``lfx.components``) keeps
emitting SpiderTool's translation keys.  Removed at the M4 shim cleanup.
"""

import importlib
import sys

try:
    sys.modules[__name__] = importlib.import_module("lfx_bundles.spider")
except ModuleNotFoundError as exc:
    if exc.name is not None and (exc.name == "lfx_bundles" or exc.name.startswith("lfx_bundles.")):
        msg = (
            "The 'spider' components moved to the 'lfx-bundles' distribution. "
            "Install it with:  pip install lfx-bundles."
        )
        raise ModuleNotFoundError(msg, name="lfx_bundles") from exc
    raise

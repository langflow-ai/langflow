"""Compatibility shim for Policies helpers moved to ``lfx-toolguard``."""

from __future__ import annotations

import importlib
import sys

try:
    sys.modules[__name__] = importlib.import_module("lfx_toolguard.components.models_and_agents.policies")
except ModuleNotFoundError as exc:
    if exc.name is not None and exc.name.partition(".")[0] != "lfx_toolguard":
        raise
    msg = (
        "The Policies helpers moved to the 'lfx-toolguard' distribution. "
        'Install them with `pip install "lfx[toolguard]"`.'
    )
    raise ModuleNotFoundError(msg) from exc

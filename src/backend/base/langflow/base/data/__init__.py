"""Backwards compatibility module for langflow.base.data."""

import contextlib

from lfx.base.data import *  # noqa: F403

# Import modules that exist only in langflow
with contextlib.suppress(ImportError):
    from . import kb_utils  # noqa: F401

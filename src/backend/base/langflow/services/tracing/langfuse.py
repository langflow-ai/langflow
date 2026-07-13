"""Compatibility re-export from the standalone ``langflow_services`` package.

Aliases this module to the concrete implementation so public and private
names, monkeypatches, and identity checks resolve to one object.
"""

from __future__ import annotations

import sys

from langflow_services.tracing import langfuse as _impl

sys.modules[__name__] = _impl

"""Compatibility re-export from the standalone ``services`` package.

Aliases this module to the concrete implementation so public and private
names, monkeypatches, and identity checks resolve to one object.
"""

from __future__ import annotations

import sys

from services.authorization import access_ceiling as _impl

sys.modules[__name__] = _impl

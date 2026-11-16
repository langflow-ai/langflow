"""Langflow's native core.

``lfx_native.ops`` is the flow operation engine. It takes Python values, or
JSON text in ``bytes``, and returns Python values. Only large calls release
the GIL.
"""

from lfx_native import ops

__all__ = ["ops"]

"""Langflow's native core.

``lfx_native.ops`` is the flow operation engine. Graphs and operations
cross into it as Python values, or as JSON text in ``bytes``, and results
come back as Python values. A call releases the GIL only for large work:
small calls keep it, so they never wait for it again.
"""

from lfx_native import ops

__all__ = ["ops"]

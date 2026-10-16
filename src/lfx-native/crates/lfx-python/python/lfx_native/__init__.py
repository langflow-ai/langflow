"""Langflow's native core.

``lfx_native.ops`` is the flow operation engine. Graphs, operations and
results cross into it as JSON text, ``str`` or ``bytes``, and come back as
JSON text. Every call releases the GIL.
"""

from lfx_native import ops

__all__ = ["ops"]

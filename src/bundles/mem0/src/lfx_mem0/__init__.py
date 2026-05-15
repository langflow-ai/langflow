"""lfx-mem0: Mem0 bundle.

Distribution unit ``lfx-mem0``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:mem0:<Class>@official``.
"""

from lfx_mem0.components.mem0.mem0_chat_memory import Mem0MemoryComponent

__all__ = [
    "Mem0MemoryComponent",
]

"""lfx-zep: Zep bundle.

Distribution unit ``lfx-zep``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:zep:<Class>@official``.
"""

from lfx_zep.components.zep.zep import ZepChatMemory

__all__ = [
    "ZepChatMemory",
]

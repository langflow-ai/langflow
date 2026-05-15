"""lfx-confluence: Confluence bundle.

Distribution unit ``lfx-confluence``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:confluence:<Class>@official``.
"""

from lfx_confluence.components.confluence.confluence import ConfluenceComponent

__all__ = [
    "ConfluenceComponent",
]

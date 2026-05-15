"""lfx-xai: Xai bundle.

Distribution unit ``lfx-xai``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:xai:<Class>@official``.
"""

from lfx_xai.components.xai.xai import XAIModelComponent

__all__ = [
    "XAIModelComponent",
]

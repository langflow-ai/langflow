"""lfx-deepseek: Deepseek bundle.

Distribution unit ``lfx-deepseek``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:deepseek:<Class>@official``.
"""

from lfx_deepseek.components.deepseek.deepseek import DeepSeekModelComponent

__all__ = [
    "DeepSeekModelComponent",
]

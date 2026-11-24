"""lfx-anthropic: Anthropic bundle.

Distribution unit ``lfx-anthropic``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:anthropic:<Class>@official``.
"""

from lfx_anthropic.components.anthropic.anthropic import AnthropicModelComponent

__all__ = [
    "AnthropicModelComponent",
]

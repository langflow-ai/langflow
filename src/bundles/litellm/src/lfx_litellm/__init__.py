"""lfx-litellm: Litellm bundle.

Distribution unit ``lfx-litellm``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:litellm:<Class>@official``.
"""

from lfx_litellm.components.litellm.litellm_proxy import LiteLLMProxyComponent

__all__ = [
    "LiteLLMProxyComponent",
]

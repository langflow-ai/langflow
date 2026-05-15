"""lfx-cloudflare: Cloudflare bundle.

Distribution unit ``lfx-cloudflare``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:cloudflare:<Class>@official``.
"""

from lfx_cloudflare.components.cloudflare.cloudflare import CloudflareWorkersAIEmbeddingsComponent

__all__ = [
    "CloudflareWorkersAIEmbeddingsComponent",
]

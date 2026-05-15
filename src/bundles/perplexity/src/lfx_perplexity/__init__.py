"""lfx-perplexity: Perplexity bundle.

Distribution unit ``lfx-perplexity``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:perplexity:<Class>@official``.
"""

from lfx_perplexity.components.perplexity.perplexity import PerplexityComponent

__all__ = [
    "PerplexityComponent",
]

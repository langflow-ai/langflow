"""lfx-mistral: Mistral bundle.

Distribution unit ``lfx-mistral``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:mistral:<Class>@official``.
"""

from lfx_mistral.components.mistral.mistral import MistralAIModelComponent
from lfx_mistral.components.mistral.mistral_embeddings import MistralAIEmbeddingsComponent

__all__ = [
    "MistralAIEmbeddingsComponent",
    "MistralAIModelComponent",
]

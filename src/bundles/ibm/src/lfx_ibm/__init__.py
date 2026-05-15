"""lfx-ibm: Ibm bundle.

Distribution unit ``lfx-ibm``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:ibm:<Class>@official``.
"""

from lfx_ibm.components.ibm.watsonx import WatsonxAIComponent
from lfx_ibm.components.ibm.watsonx_embeddings import WatsonxEmbeddingsComponent

__all__ = [
    "WatsonxAIComponent",
    "WatsonxEmbeddingsComponent",
]

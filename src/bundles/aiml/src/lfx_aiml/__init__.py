"""lfx-aiml: Aiml bundle.

Distribution unit ``lfx-aiml``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:aiml:<Class>@official``.
"""

from lfx_aiml.components.aiml.aiml import AIMLModelComponent
from lfx_aiml.components.aiml.aiml_embeddings import AIMLEmbeddingsComponent

__all__ = [
    "AIMLEmbeddingsComponent",
    "AIMLModelComponent",
]

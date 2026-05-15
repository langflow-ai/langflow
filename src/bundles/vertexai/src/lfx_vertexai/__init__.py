"""lfx-vertexai: Vertexai bundle.

Distribution unit ``lfx-vertexai``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:vertexai:<Class>@official``.
"""

from lfx_vertexai.components.vertexai.vertexai import ChatVertexAIComponent
from lfx_vertexai.components.vertexai.vertexai_embeddings import VertexAIEmbeddingsComponent

__all__ = [
    "ChatVertexAIComponent",
    "VertexAIEmbeddingsComponent",
]

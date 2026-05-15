"""lfx-ollama: Ollama bundle.

Distribution unit ``lfx-ollama``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:ollama:<Class>@official``.
"""

from lfx_ollama.components.ollama.ollama import ChatOllamaComponent
from lfx_ollama.components.ollama.ollama_embeddings import OllamaEmbeddingsComponent

__all__ = [
    "ChatOllamaComponent",
    "OllamaEmbeddingsComponent",
]

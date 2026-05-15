"""lfx-vllm: Vllm bundle.

Distribution unit ``lfx-vllm``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:vllm:<Class>@official``.
"""

from lfx_vllm.components.vllm.vllm import VllmComponent
from lfx_vllm.components.vllm.vllm_embeddings import VllmEmbeddingsComponent

__all__ = [
    "VllmComponent",
    "VllmEmbeddingsComponent",
]

"""Component re-exports for the ``nextplaid`` bundle.

Saved-flow migration entries that target ``lfx.components.nextplaid.<Class>``
(and the legacy ``lfx.components.vllm.<Class>`` path for the multivector
embeddings) resolve through this package, so the moved Component classes must
be importable from here by name.
"""

from .nextplaid import NextPlaidVectorStoreComponent
from .vllm_multivector_embeddings import VllmMultivectorEmbeddingsComponent

__all__ = [
    "NextPlaidVectorStoreComponent",
    "VllmMultivectorEmbeddingsComponent",
]

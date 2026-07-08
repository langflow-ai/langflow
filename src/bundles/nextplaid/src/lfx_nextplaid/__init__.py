"""lfx-nextplaid: NextPlaid multi-vector vector store bundle.

This package is the distribution unit ``lfx-nextplaid``.  At runtime
Langflow's loader discovers ``extension.json`` shipped alongside this
``__init__.py`` and registers the bundle's two components under the
namespaced IDs:

* ``ext:nextplaid:NextPlaidVectorStoreComponent@official``
* ``ext:nextplaid:VllmMultivectorEmbeddingsComponent@official``

NextPlaid stores each document as a matrix of token embeddings
(ColBERT/ColPali-style late interaction, MaxSim scoring) backed by a
running NextPlaid server via the ``langchain-plaid`` client.  The
companion ``VllmMultivectorEmbeddings`` component produces the token-matrix
embeddings NextPlaid ingests by calling vLLM's ``/pooling`` endpoint; the
two ship together because the multivector embeddings exist to feed
NextPlaid.
"""

from lfx_nextplaid.components.nextplaid.nextplaid import NextPlaidVectorStoreComponent
from lfx_nextplaid.components.nextplaid.vllm_multivector_embeddings import VllmMultivectorEmbeddingsComponent

__all__ = [
    "NextPlaidVectorStoreComponent",
    "VllmMultivectorEmbeddingsComponent",
]

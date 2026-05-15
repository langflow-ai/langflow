"""lfx-elastic: Elastic bundle.

Distribution unit ``lfx-elastic``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:elastic:<Class>@official``.
"""

from lfx_elastic.components.elastic.elasticsearch import ElasticsearchVectorStoreComponent
from lfx_elastic.components.elastic.opensearch import OpenSearchVectorStoreComponent
from lfx_elastic.components.elastic.opensearch_multimodal import OpenSearchVectorStoreComponentMultimodalMultiEmbedding

__all__ = [
    "ElasticsearchVectorStoreComponent",
    "OpenSearchVectorStoreComponent",
    "OpenSearchVectorStoreComponentMultimodalMultiEmbedding",
]

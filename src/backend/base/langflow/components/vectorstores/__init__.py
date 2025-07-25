from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langflow.components._importing import import_mod

if TYPE_CHECKING:
    from .astradb import AstraDBVectorStoreComponent
    from .astradb_graph import AstraDBGraphVectorStoreComponent
    from .cassandra import CassandraVectorStoreComponent
    from .cassandra_graph import CassandraGraphVectorStoreComponent
    from .chroma import ChromaVectorStoreComponent
    from .clickhouse import ClickhouseVectorStoreComponent
    from .couchbase import CouchbaseVectorStoreComponent
    from .elasticsearch import ElasticsearchVectorStoreComponent
    from .faiss import FaissVectorStoreComponent
    from .graph_rag import GraphRAGComponent
    from .hcd import HCDVectorStoreComponent
    from .local_db import LocalDBComponent
    from .milvus import MilvusVectorStoreComponent
    from .mongodb_atlas import MongoVectorStoreComponent
    from .opensearch import OpenSearchVectorStoreComponent
    from .pgvector import PGVectorStoreComponent
    from .pinecone import PineconeVectorStoreComponent
    from .qdrant import QdrantVectorStoreComponent
    from .redis import RedisVectorStoreComponent
    from .supabase import SupabaseVectorStoreComponent
    from .upstash import UpstashVectorStoreComponent
    from .vectara import VectaraVectorStoreComponent
    from .vectara_rag import VectaraRagComponent
    from .weaviate import WeaviateVectorStoreComponent

_dynamic_imports = {
    "AstraDBVectorStoreComponent": "astradb",
    "AstraDBGraphVectorStoreComponent": "astradb_graph",
    "CassandraVectorStoreComponent": "cassandra",
    "CassandraGraphVectorStoreComponent": "cassandra_graph",
    "ChromaVectorStoreComponent": "chroma",
    "ClickhouseVectorStoreComponent": "clickhouse",
    "CouchbaseVectorStoreComponent": "couchbase",
    "ElasticsearchVectorStoreComponent": "elasticsearch",
    "FaissVectorStoreComponent": "faiss",
    "GraphRAGComponent": "graph_rag",
    "HCDVectorStoreComponent": "hcd",
    "LocalDBComponent": "local_db",
    "MilvusVectorStoreComponent": "milvus",
    "MongoVectorStoreComponent": "mongodb_atlas",
    "OpenSearchVectorStoreComponent": "opensearch",
    "PGVectorStoreComponent": "pgvector",
    "PineconeVectorStoreComponent": "pinecone",
    "QdrantVectorStoreComponent": "qdrant",
    "RedisVectorStoreComponent": "redis",
    "SupabaseVectorStoreComponent": "supabase",
    "UpstashVectorStoreComponent": "upstash",
    "VectaraVectorStoreComponent": "vectara",
    "VectaraRagComponent": "vectara_rag",
    "WeaviateVectorStoreComponent": "weaviate",
}

__all__ = [
    "AstraDBGraphVectorStoreComponent",
    "AstraDBVectorStoreComponent",
    "CassandraGraphVectorStoreComponent",
    "CassandraVectorStoreComponent",
    "ChromaVectorStoreComponent",
    "ClickhouseVectorStoreComponent",
    "CouchbaseVectorStoreComponent",
    "ElasticsearchVectorStoreComponent",
    "FaissVectorStoreComponent",
    "GraphRAGComponent",
    "HCDVectorStoreComponent",
    "LocalDBComponent",
    "MilvusVectorStoreComponent",
    "MongoVectorStoreComponent",
    "OpenSearchVectorStoreComponent",
    "PGVectorStoreComponent",
    "PineconeVectorStoreComponent",
    "QdrantVectorStoreComponent",
    "RedisVectorStoreComponent",
    "SupabaseVectorStoreComponent",
    "UpstashVectorStoreComponent",
    "VectaraRagComponent",
    "VectaraVectorStoreComponent",
    "WeaviateVectorStoreComponent",
]


def __getattr__(attr_name: str) -> Any:
    """Lazily import vectorstore components on attribute access."""
    if attr_name not in _dynamic_imports:
        msg = f"module '{__name__}' has no attribute '{attr_name}'"
        raise AttributeError(msg)
    try:
        result = import_mod(attr_name, _dynamic_imports[attr_name], __spec__.parent)
    except (ModuleNotFoundError, ImportError, AttributeError) as e:
        msg = f"Could not import '{attr_name}' from '{__name__}': {e}"
        raise AttributeError(msg) from e
    globals()[attr_name] = result
    return result


def __dir__() -> list[str]:
    return list(__all__)

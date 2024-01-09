from langflow import CustomComponent
from langchain_community.vectorstores.qdrant import Qdrant
from typing import Optional, List
from langflow.field_typing import Document, Embeddings, NestedDict


class QdrantComponent(CustomComponent):
    display_name = "Qdrant"
    description = "Construct Qdrant wrapper from a list of texts."

    def build_config(self):
        return {
            "documents": {"display_name": "Documents"},
            "embedding": {"display_name": "Embedding"},
            "api_key": {"display_name": "API Key", "password": True},
            "collection_name": {"display_name": "Collection Name"},
            "content_payload_key": {"display_name": "Content Payload Key"},
            "distance_func": {"display_name": "Distance Function"},
            "grpc_port": {"display_name": "gRPC Port"},
            "host": {"display_name": "Host"},
            "https": {"display_name": "HTTPS"},
            "location": {"display_name": "Location"},
            "metadata_payload_key": {"display_name": "Metadata Payload Key"},
            "path": {"display_name": "Path"},
            "port": {"display_name": "Port"},
            "prefer_grpc": {"display_name": "Prefer gRPC"},
            "prefix": {"display_name": "Prefix"},
            "search_kwargs": {"display_name": "Search Kwargs"},
            "timeout": {"display_name": "Timeout"},
            "url": {"display_name": "URL"},
        }

    def build(
        self,
        embedding: Embeddings,
        documents: Optional[List[Document]] = None,
        api_key: Optional[str] = None,
        collection_name: Optional[str] = None,
        content_payload_key: str = "page_content",
        distance_func: str = "Cosine",
        grpc_port: int = 6334,
        host: Optional[str] = None,
        https: bool = False,
        location: str = ":memory:",
        metadata_payload_key: str = "metadata",
        path: Optional[str] = None,
        port: int = 6333,
        prefer_grpc: bool = False,
        prefix: Optional[str] = None,
        search_kwargs: Optional[NestedDict] = None,
        timeout: Optional[float] = None,
        url: Optional[str] = None,
    ) -> Qdrant:
        return Qdrant(
            documents=documents,
            embedding=embedding,
            api_key=api_key,
            collection_name=collection_name,
            content_payload_key=content_payload_key,
            distance_func=distance_func,
            grpc_port=grpc_port,
            host=host,
            https=https,
            location=location,
            metadata_payload_key=metadata_payload_key,
            path=path,
            port=port,
            prefer_grpc=prefer_grpc,
            prefix=prefix,
            search_kwargs=search_kwargs,
            timeout=timeout,
            url=url,
        )

from typing import List, Optional

from langflow.components.vectorstores.base.model import LCVectorStoreComponent
from langflow.components.vectorstores.Qdrant import QdrantComponent
from langflow.field_typing import Embeddings, NestedDict, Text
from langflow.schema import Record


class QdrantSearchComponent(QdrantComponent, LCVectorStoreComponent):
    display_name = "Qdrant Search"
    description = "Construct Qdrant wrapper from a list of texts."
    icon = "Qdrant"

    def build_config(self):
        return {
            "search_type": {
                "display_name": "Search Type",
                "options": ["Similarity", "MMR"],
            },
            "input_value": {"display_name": "Input"},
            "embedding": {"display_name": "Embedding"},
            "api_key": {"display_name": "API Key", "password": True, "advanced": True},
            "collection_name": {"display_name": "Collection Name"},
            "content_payload_key": {
                "display_name": "Content Payload Key",
                "advanced": True,
            },
            "distance_func": {"display_name": "Distance Function", "advanced": True},
            "grpc_port": {"display_name": "gRPC Port", "advanced": True},
            "host": {"display_name": "Host", "advanced": True},
            "https": {"display_name": "HTTPS", "advanced": True},
            "location": {"display_name": "Location", "advanced": True},
            "metadata_payload_key": {
                "display_name": "Metadata Payload Key",
                "advanced": True,
            },
            "path": {"display_name": "Path", "advanced": True},
            "port": {"display_name": "Port", "advanced": True},
            "prefer_grpc": {"display_name": "Prefer gRPC", "advanced": True},
            "prefix": {"display_name": "Prefix", "advanced": True},
            "search_kwargs": {"display_name": "Search Kwargs", "advanced": True},
            "timeout": {"display_name": "Timeout", "advanced": True},
            "url": {"display_name": "URL", "advanced": True},
            "number_of_results": {
                "display_name": "Number of Results",
                "info": "Number of results to return.",
                "advanced": True,
            },
        }

    def build(  # type: ignore[override]
        self,
        input_value: Text,
        embedding: Embeddings,
        collection_name: str,
        number_of_results: int = 4,
        search_type: str = "similarity",
        api_key: Optional[str] = None,
        content_payload_key: str = "page_content",
        distance_func: str = "Cosine",
        grpc_port: int = 6334,
        https: bool = False,
        host: Optional[str] = None,
        location: Optional[str] = None,
        metadata_payload_key: str = "metadata",
        path: Optional[str] = None,
        port: Optional[int] = 6333,
        prefer_grpc: bool = False,
        prefix: Optional[str] = None,
        search_kwargs: Optional[NestedDict] = None,
        timeout: Optional[int] = None,
        url: Optional[str] = None,
    ) -> List[Record]:  # type: ignore[override]
        vector_store = super().build(
            embedding=embedding,
            collection_name=collection_name,
            api_key=api_key,
            content_payload_key=content_payload_key,
            distance_func=distance_func,
            grpc_port=grpc_port,
            https=https,
            host=host,
            location=location,
            metadata_payload_key=metadata_payload_key,
            path=path,
            port=port,
            prefer_grpc=prefer_grpc,
            prefix=prefix,
            timeout=timeout,
            url=url,
        )
        if not vector_store:
            raise ValueError("Failed to load the Qdrant index.")
        if search_kwargs is None:
            search_kwargs = {}

        return self.search_with_vector_store(
            vector_store=vector_store,
            input_value=input_value,
            search_type=search_type,
            k=number_of_results,
            **search_kwargs,
        )

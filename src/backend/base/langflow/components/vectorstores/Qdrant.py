from typing import Optional, Union

from langchain.schema import BaseRetriever
from langchain_community.vectorstores import VectorStore
from langchain_community.vectorstores.qdrant import Qdrant

from langflow.field_typing import Embeddings
from langflow.interface.custom.custom_component import CustomComponent
from langflow.schema.schema import Record


class QdrantComponent(CustomComponent):
    display_name = "Qdrant"
    description = "Construct Qdrant wrapper from a list of texts."
    icon = "Qdrant"

    def build_config(self):
        return {
            "inputs": {"display_name": "Input", "input_types": ["Document", "Record"]},
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
            "timeout": {"display_name": "Timeout", "advanced": True},
            "url": {"display_name": "URL", "advanced": True},
        }

    def build(
        self,
        embedding: Embeddings,
        collection_name: str,
        inputs: Optional[Record] = None,
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
        timeout: Optional[int] = None,
        url: Optional[str] = None,
    ) -> Union[VectorStore, Qdrant, BaseRetriever]:
        documents = []
        for _input in inputs or []:
            if isinstance(_input, Record):
                documents.append(_input.to_lc_document())
            else:
                documents.append(_input)
        if documents is None:
            from qdrant_client import QdrantClient

            client = QdrantClient(
                location=location,
                url=host,
                port=port,
                grpc_port=grpc_port,
                https=https,
                prefix=prefix,
                timeout=timeout,
                prefer_grpc=prefer_grpc,
                metadata_payload_key=metadata_payload_key,
                content_payload_key=content_payload_key,
                api_key=api_key,
                collection_name=collection_name,
                host=host,
                path=path,
            )
            vs = Qdrant(
                client=client,
                collection_name=collection_name,
                embeddings=embedding,
            )
            return vs
        else:
            vs = Qdrant.from_documents(
                documents=documents,  # type: ignore
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
                timeout=timeout,
                url=url,
            )
        return vs

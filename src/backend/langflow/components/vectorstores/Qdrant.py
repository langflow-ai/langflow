from typing import List, Optional, Union
from langflow import CustomComponent

from langchain.vectorstores import Qdrant
from langchain.vectorstores.base import VectorStore
from langchain.schema import BaseRetriever
from langchain.schema import Document
from langchain.embeddings.base import Embeddings
from qdrant_client import QdrantClient


class QdrantComponent(CustomComponent):
    display_name: str = "Qdrant (Custom Component)"
    description: str = "Implementation of Vector Store using Qdrant"
    documentation = "https://python.langchain.com/docs/integrations/vectorstores/qdrant"
    beta = True

    def build_config(self):
        return {
            "collection_name": {
                "display_name": "Collection Name",
                "value": "langflow",
            },
            "persistence": {
                "display_name": "Persistence",
                "options": ["In-Memory", "On-Disk", "Container", "Qdrant Cloud"],
                "value": "In-Memory",
            },
            "path": {"display_name": "Path", "required": False},
            "url": {"display_name": "URL", "required": False},
            "api_key": {
                "display_name": "Qdrant Cloud API Key",
                "password": True,
                "required": False,
            },
            "prefer_grpc": {
                "display_name": "Prefer gRPC",
                "advanced": True,
                "value": True,
            },
            "documents": {"display_name": "Documents", "is_list": True},
            "embedding": {"display_name": "Embeddings"},
            "code": {"display_name": "Code", "show": False},
        }

    def build(
        self,
        collection_name: str,
        persistence: str,
        path: Optional[str] = None,
        url: Optional[str] = None,
        api_key: Optional[str] = None,
        prefer_grpc: bool = True,
        embedding: Optional[Embeddings] = None,
        documents: Optional[List[Document]] = None,
    ) -> Union[VectorStore, BaseRetriever]:
        """
        def initialize_qdrant(class_object: Type[Qdrant], params: dict):
        if not docs_in_params(params):
            if "location" not in params and "api_key" not in params:
                raise ValueError("Location and API key must be provided in the params")
            from qdrant_client import QdrantClient

            client_params = {
                "location": params.pop("location"),
                "api_key": params.pop("api_key"),
            }
            lc_params = {
                "collection_name": params.pop("collection_name"),
                "embeddings": params.pop("embedding"),
            }
            client = QdrantClient(**client_params)

            return class_object(client=client, **lc_params)

        return class_object.from_documents(**params)
        """

        if persistence == "On-Disk":
            if not path:
                raise ValueError("Path is required for On-Disk persistence")
            if documents and embedding:
                return Qdrant.from_documents(
                    documents=documents,
                    embedding=embedding,
                    collection_name=collection_name,
                    path=path,
                )

        elif persistence == "Container":
            if not url:
                raise ValueError("URL is required for Container persistence")
            if documents and embedding:
                return Qdrant.from_documents(
                    documents=documents,
                    embedding=embedding,
                    collection_name=collection_name,
                    prefer_grpc=prefer_grpc,
                    url=url,
                )

        elif persistence == "Qdrant Cloud":
            if not url or not api_key:
                raise ValueError(
                    "URL and Qdrant Cloud API Key are required for Qdrant Cloud"
                )
            if documents and embedding:
                return Qdrant.from_documents(
                    documents=documents,
                    embedding=embedding,
                    collection_name=collection_name,
                    prefer_grpc=prefer_grpc,
                    url=url,
                    api_key=api_key,
                )

        # In-Memory
        elif documents and embedding:
            return Qdrant.from_documents(
                documents=documents,
                embedding=embedding,
                collection_name=collection_name,
                location=":memory:",
            )

        return Qdrant(
            embeddings=embedding,
            collection_name=collection_name,
            client=QdrantClient(
                location=":memory:" if persistence == "In-Memory" else None,
                api_key=api_key if persistence == "Qdrant Cloud" else None,
            ),
        )

from typing import Optional, Union
from langflow import CustomComponent

from langchain.vectorstores import Chroma
from langchain.schema import Document
from langchain.vectorstores.base import VectorStore
from langchain.schema import BaseRetriever
from langchain.embeddings.base import Embeddings
import chromadb  # type: ignore


class ChromaComponent(CustomComponent):
    """
    A custom component for implementing a Vector Store using Chroma.
    """

    display_name: str = "Chroma (Custom Component)"
    description: str = "Implementation of Vector Store using Chroma"
    documentation = "https://python.langchain.com/docs/integrations/vectorstores/chroma"
    beta = True

    def build_config(self):
        """
        Builds the configuration for the component.

        Returns:
        - dict: A dictionary containing the configuration options for the component.
        """
        return {
            "collection_name": {"display_name": "Collection Name", "value": "langflow"},
            "persist": {"display_name": "Persist"},
            "persist_directory": {"display_name": "Persist Directory"},
            "code": {"show": False, "display_name": "Code"},
            "documents": {"display_name": "Documents", "is_list": True},
            "embedding": {"display_name": "Embedding"},
            "chroma_server_cors_allow_origins": {
                "display_name": "Server CORS Allow Origins",
                "advanced": True,
            },
            "chroma_server_host": {"display_name": "Server Host", "advanced": True},
            "chroma_server_port": {"display_name": "Server Port", "advanced": True},
            "chroma_server_grpc_port": {
                "display_name": "Server gRPC Port",
                "advanced": True,
            },
            "chroma_server_ssl_enabled": {
                "display_name": "Server SSL Enabled",
                "advanced": True,
            },
        }

    def build(
        self,
        collection_name: str,
        persist: bool,
        chroma_server_ssl_enabled: bool,
        persist_directory: Optional[str] = None,
        embedding: Optional[Embeddings] = None,
        documents: Optional[Document] = None,
        chroma_server_cors_allow_origins: Optional[str] = None,
        chroma_server_host: Optional[str] = None,
        chroma_server_port: Optional[int] = None,
        chroma_server_grpc_port: Optional[int] = None,
    ) -> Union[VectorStore, BaseRetriever]:
        """
        Builds the Vector Store or BaseRetriever object.

        Args:
        - collection_name (str): The name of the collection.
        - persist_directory (Optional[str]): The directory to persist the Vector Store to.
        - chroma_server_ssl_enabled (bool): Whether to enable SSL for the Chroma server.
        - persist (bool): Whether to persist the Vector Store or not.
        - embedding (Optional[Embeddings]): The embeddings to use for the Vector Store.
        - documents (Optional[Document]): The documents to use for the Vector Store.
        - chroma_server_cors_allow_origins (Optional[str]): The CORS allow origins for the Chroma server.
        - chroma_server_host (Optional[str]): The host for the Chroma server.
        - chroma_server_port (Optional[int]): The port for the Chroma server.
        - chroma_server_grpc_port (Optional[int]): The gRPC port for the Chroma server.

        Returns:
        - Union[VectorStore, BaseRetriever]: The Vector Store or BaseRetriever object.
        """

        # Chroma settings
        chroma_settings = None

        if chroma_server_host is not None:
            chroma_settings = chromadb.config.Settings(
                chroma_server_cors_allow_origins=chroma_server_cors_allow_origins
                or None,
                chroma_server_host=chroma_server_host,
                chroma_server_port=chroma_server_port or None,
                chroma_server_grpc_port=chroma_server_grpc_port or None,
                chroma_server_ssl_enabled=chroma_server_ssl_enabled,
            )

        # If documents, then we need to create a Chroma instance using .from_documents
        if documents is not None and embedding is not None:
            return Chroma.from_documents(
                documents=documents,  # type: ignore
                persist_directory=persist_directory if persist else None,
                collection_name=collection_name,
                embedding=embedding,
                client_settings=chroma_settings,
            )

        return Chroma(
            persist_directory=persist_directory, client_settings=chroma_settings
        )

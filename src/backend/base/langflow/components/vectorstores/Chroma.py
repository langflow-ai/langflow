from typing import List, Optional, Union

import chromadb  # type: ignore
from langchain.embeddings.base import Embeddings
from langchain.schema import BaseRetriever
from langchain_community.vectorstores import VectorStore
from langchain_community.vectorstores.chroma import Chroma

from langflow.interface.custom.custom_component import CustomComponent
from langflow.schema.schema import Record


class ChromaComponent(CustomComponent):
    """
    A custom component for implementing a Vector Store using Chroma.
    """

    display_name: str = "Chroma"
    description: str = "Implementation of Vector Store using Chroma"
    documentation = "https://python.langchain.com/docs/integrations/vectorstores/chroma"
    icon = "Chroma"

    def build_config(self):
        """
        Builds the configuration for the component.

        Returns:
        - dict: A dictionary containing the configuration options for the component.
        """
        return {
            "collection_name": {"display_name": "Collection Name", "value": "langflow"},
            "index_directory": {"display_name": "Persist Directory"},
            "code": {"advanced": True, "display_name": "Code"},
            "inputs": {"display_name": "Input", "input_types": ["Document", "Record"]},
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
        embedding: Embeddings,
        chroma_server_ssl_enabled: bool,
        index_directory: Optional[str] = None,
        inputs: Optional[List[Record]] = None,
        chroma_server_cors_allow_origins: Optional[str] = None,
        chroma_server_host: Optional[str] = None,
        chroma_server_port: Optional[int] = None,
        chroma_server_grpc_port: Optional[int] = None,
    ) -> Union[VectorStore, BaseRetriever]:
        """
        Builds the Vector Store or BaseRetriever object.

        Args:
        - collection_name (str): The name of the collection.
        - index_directory (Optional[str]): The directory to persist the Vector Store to.
        - chroma_server_ssl_enabled (bool): Whether to enable SSL for the Chroma server.
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
                chroma_server_cors_allow_origins=chroma_server_cors_allow_origins or None,
                chroma_server_host=chroma_server_host,
                chroma_server_port=chroma_server_port or None,
                chroma_server_grpc_port=chroma_server_grpc_port or None,
                chroma_server_ssl_enabled=chroma_server_ssl_enabled,
            )

        # If documents, then we need to create a Chroma instance using .from_documents

        # Check index_directory and expand it if it is a relative path
        if index_directory is not None:
            index_directory = self.resolve_path(index_directory)

        documents = []
        for _input in inputs or []:
            if isinstance(_input, Record):
                documents.append(_input.to_lc_document())
            else:
                documents.append(_input)
        if documents is not None and embedding is not None:
            if len(documents) == 0:
                raise ValueError("If documents are provided, there must be at least one document.")
            chroma = Chroma.from_documents(
                documents=documents,  # type: ignore
                persist_directory=index_directory,
                collection_name=collection_name,
                embedding=embedding,
                client_settings=chroma_settings,
            )
        else:
            chroma = Chroma(
                persist_directory=index_directory,
                client_settings=chroma_settings,
                embedding_function=embedding,
            )
        return chroma

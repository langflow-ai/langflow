from copy import deepcopy
from typing import List, Optional, Union

import chromadb
from chromadb.config import Settings
from langchain_chroma import Chroma
from langchain_core.embeddings import Embeddings
from langchain_core.retrievers import BaseRetriever
from langchain_core.vectorstores import VectorStore

from langflow.base.vectorstores.utils import chroma_collection_to_records
from langflow.custom import CustomComponent
from langflow.schema import Record


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
            "chroma_server_http_port": {"display_name": "Server HTTP Port", "advanced": True},
            "chroma_server_grpc_port": {
                "display_name": "Server gRPC Port",
                "advanced": True,
            },
            "chroma_server_ssl_enabled": {
                "display_name": "Server SSL Enabled",
                "advanced": True,
            },
            "allow_duplicates": {
                "display_name": "Allow Duplicates",
                "advanced": True,
                "info": "If false, will not add documents that are already in the Vector Store.",
            },
        }

    def build(
        self,
        collection_name: str,
        embedding: Embeddings,
        chroma_server_ssl_enabled: bool,
        index_directory: Optional[str] = None,
        inputs: Optional[List[Record]] = None,
        chroma_server_cors_allow_origins: List[str] = [],
        chroma_server_host: Optional[str] = None,
        chroma_server_http_port: Optional[int] = None,
        chroma_server_grpc_port: Optional[int] = None,
        allow_duplicates: bool = False,
    ) -> Union[VectorStore, BaseRetriever]:
        """
        Builds the Vector Store or BaseRetriever object.

        Args:
        - collection_name (str): The name of the collection.
        - embedding (Embeddings): The embeddings to use for the Vector Store.
        - chroma_server_ssl_enabled (bool): Whether to enable SSL for the Chroma server.
        - index_directory (Optional[str]): The directory to persist the Vector Store to.
        - inputs (Optional[List[Record]]): The input records to use for the Vector Store.
        - chroma_server_cors_allow_origins (List[str]): The CORS allow origins for the Chroma server.
        - chroma_server_host (Optional[str]): The host for the Chroma server.
        - chroma_server_http_port (Optional[int]): The HTTP port for the Chroma server.
        - chroma_server_grpc_port (Optional[int]): The gRPC port for the Chroma server.
        - allow_duplicates (bool): Whether to allow duplicates in the Vector Store.

        Returns:
        - Union[VectorStore, BaseRetriever]: The Vector Store or BaseRetriever object.
        """

        # Chroma settings
        chroma_settings = None
        client = None
        if chroma_server_host is not None:
            chroma_settings = Settings(
                chroma_server_cors_allow_origins=chroma_server_cors_allow_origins or [],
                chroma_server_host=chroma_server_host,
                chroma_server_http_port=chroma_server_http_port or None,
                chroma_server_grpc_port=chroma_server_grpc_port or None,
                chroma_server_ssl_enabled=chroma_server_ssl_enabled,
            )
            client = chromadb.HttpClient(settings=chroma_settings)

        # Check index_directory and expand it if it is a relative path
        if index_directory is not None:
            index_directory = self.resolve_path(index_directory)

        chroma = Chroma(
            persist_directory=index_directory,
            client=client,
            embedding_function=embedding,
            collection_name=collection_name,
        )
        if allow_duplicates:
            stored_records = []
        else:
            stored_records = chroma_collection_to_records(chroma.get())
            _stored_documents_without_id = []
            for record in deepcopy(stored_records):
                del record.id
                _stored_documents_without_id.append(record)
        documents = []
        for _input in inputs or []:
            if isinstance(_input, Record):
                if _input not in _stored_documents_without_id:
                    documents.append(_input.to_lc_document())
            else:
                raise ValueError("Inputs must be a Record objects.")

        if documents and embedding is not None:
            chroma.add_documents(documents)

        self.status = stored_records
        return chroma

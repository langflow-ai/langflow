from typing import List, Optional

import chromadb  # type: ignore
from langchain_community.vectorstores.chroma import Chroma

from langflow.components.vectorstores.base.model import LCVectorStoreComponent
from langflow.field_typing import Embeddings, Text
from langflow.schema import Record


class ChromaSearchComponent(LCVectorStoreComponent):
    display_name: str = "Chroma Search"
    description: str = "Search a Chroma collection for similar documents."
    icon = "Chroma"

    def build_config(self):
        """
        Builds the configuration for the component.

        Returns:
        - dict: A dictionary containing the configuration options for the component.
        """
        return {
            "input_value": {"display_name": "Input"},
            "search_type": {
                "display_name": "Search Type",
                "options": ["Similarity", "MMR"],
            },
            "collection_name": {"display_name": "Collection Name", "value": "langflow"},
            # "persist": {"display_name": "Persist"},
            "index_directory": {"display_name": "Index Directory"},
            "code": {"show": False, "display_name": "Code"},
            "embedding": {
                "display_name": "Embedding",
                "info": "Embedding model to vectorize inputs (make sure to use same as index)",
            },
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
            "number_of_results": {
                "display_name": "Number of Results",
                "info": "Number of results to return.",
                "advanced": True,
            },
        }

    def build(
        self,
        input_value: Text,
        search_type: str,
        collection_name: str,
        embedding: Embeddings,
        chroma_server_ssl_enabled: bool,
        number_of_results: int = 4,
        index_directory: Optional[str] = None,
        chroma_server_cors_allow_origins: Optional[str] = None,
        chroma_server_host: Optional[str] = None,
        chroma_server_port: Optional[int] = None,
        chroma_server_grpc_port: Optional[int] = None,
    ) -> List[Record]:
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
                chroma_server_cors_allow_origins=chroma_server_cors_allow_origins or None,
                chroma_server_host=chroma_server_host,
                chroma_server_port=chroma_server_port or None,
                chroma_server_grpc_port=chroma_server_grpc_port or None,
                chroma_server_ssl_enabled=chroma_server_ssl_enabled,
            )
        if index_directory:
            index_directory = self.resolve_path(index_directory)
        vector_store = Chroma(
            embedding_function=embedding,
            collection_name=collection_name,
            persist_directory=index_directory,
            client_settings=chroma_settings,
        )

        return self.search_with_vector_store(input_value, search_type, vector_store, k=number_of_results)

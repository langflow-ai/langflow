from typing import List, Optional

import chromadb
from chromadb.config import Settings
from langchain_chroma import Chroma

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
            "chroma_server_http_port": {"display_name": "Server HTTP Port", "advanced": True},
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
        chroma_server_cors_allow_origins: List[str] = [],
        chroma_server_host: Optional[str] = None,
        chroma_server_http_port: Optional[int] = None,
        chroma_server_grpc_port: Optional[int] = None,
    ) -> List[Record]:
        """
        Builds the Vector Store or BaseRetriever object.

        Args:
        - input_value (Text): The input value.
        - search_type (str): The type of search.
        - collection_name (str): The name of the collection.
        - embedding (Embeddings): The embeddings to use for the Vector Store.
        - chroma_server_ssl_enabled (bool): Whether to enable SSL for the Chroma server.
        - number_of_results (int, optional): The number of results to retrieve. Defaults to 4.
        - index_directory (str, optional): The directory to persist the Vector Store to. Defaults to None.
        - chroma_server_cors_allow_origins (List[str], optional): The CORS allow origins for the Chroma server. Defaults to [].
        - chroma_server_host (str, optional): The host for the Chroma server. Defaults to None.
        - chroma_server_http_port (int, optional): The HTTP port for the Chroma server. Defaults to None.
        - chroma_server_grpc_port (int, optional): The gRPC port for the Chroma server. Defaults to None.

        Returns:
        - List[Record]: The list of records.
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
        if index_directory:
            index_directory = self.resolve_path(index_directory)
        vector_store = Chroma(
            embedding_function=embedding,
            collection_name=collection_name,
            persist_directory=index_directory,
            client=client,
        )

        return self.search_with_vector_store(input_value, search_type, vector_store, k=number_of_results)

from typing import Optional, List
from langflow import CustomComponent

from langchain.vectorstores.pgvector import PGVector
from langchain.schema import Document
from langchain.vectorstores.base import VectorStore
from langchain.embeddings.base import Embeddings


class PostgresqlVectorComponent(CustomComponent):
    """
    A custom component for implementing a Vector Store using PostgreSQL.
    """

    display_name: str = "PGVector"
    description: str = "Implementation of Vector Store using PostgreSQL"
    documentation = (
        "https://python.langchain.com/docs/integrations/vectorstores/pgvector"
    )
    beta = True

    def build_config(self):
        """
        Builds the configuration for the component.

        Returns:
        - dict: A dictionary containing the configuration options for the component.
        """
        return {
            "index_name": {"display_name": "Index Name", "value": "your_index"},
            "code": {"show": True, "display_name": "Code"},
            "documents": {"display_name": "Documents", "is_list": True},
            "embedding": {"display_name": "Embedding"},
            "pg_server_url": {
                "display_name": "PostgreSQL Server Connection String",
                "advanced": False,
            },
            "collection_name": {"display_name": "Table", "advanced": False},
        }

    def build(
        self,
        embedding: Embeddings,
        pg_server_url: str,
        collection_name: str,
        documents: Optional[List[Document]] = None,
    ) -> VectorStore:
        """
        Builds the Vector Store or BaseRetriever object.

        Args:
        - embedding (Embeddings): The embeddings to use for the Vector Store.
        - documents (Optional[Document]): The documents to use for the Vector Store.
        - collection_name (str): The name of the PG table.
        - pg_server_url (str): The URL for the PG server.

        Returns:
        - VectorStore: The Vector Store object.
        """

        try:
            if documents is None:
                return PGVector.from_existing_index(
                    embedding=embedding,
                    collection_name=collection_name,
                    connection_string=pg_server_url,
                )

            return PGVector.from_documents(
                embedding=embedding,
                documents=documents,
                collection_name=collection_name,
                connection_string=pg_server_url,
            )
        except Exception as e:
            raise RuntimeError(f"Failed to build PGVector: {e}")

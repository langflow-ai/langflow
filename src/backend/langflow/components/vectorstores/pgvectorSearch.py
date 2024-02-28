from typing import List, Optional

from langchain.embeddings.base import Embeddings
from langchain_community.vectorstores.pgvector import PGVector

from langflow.components.vectorstores.base.model import LCVectorStoreComponent
from langflow.schema import Record


class PGVectorSearchComponent(LCVectorStoreComponent):
    """
    A custom component for implementing a Vector Store using PostgreSQL.
    """

    display_name: str = "PGVector Search"
    description: str = "Search a PGVector Store for similar documents."
    documentation = (
        "https://python.langchain.com/docs/integrations/vectorstores/pgvector"
    )

    def build_config(self):
        """
        Builds the configuration for the component.

        Returns:
        - dict: A dictionary containing the configuration options for the component.
        """
        return {
            "code": {"show": False},
            "embedding": {"display_name": "Embedding"},
            "search_type": {
                "display_name": "Search Type",
                "options": ["Similarity", "MMR"],
            },
            "pg_server_url": {
                "display_name": "PostgreSQL Server Connection String",
                "advanced": False,
            },
            "collection_name": {"display_name": "Table", "advanced": False},
            "input_value": {"display_name": "Input"},
        }

    def build(
        self,
        input_value: str,
        embedding: Embeddings,
        pg_server_url: str,
        collection_name: str,
        search_type: Optional[str] = None,
    ) -> List[Record]:
        """
        Builds the Vector Store or BaseRetriever object.

        Args:
        - input_value (str): The input value to search for.
        - embedding (Embeddings): The embeddings to use for the Vector Store.
        - collection_name (str): The name of the PG table.
        - pg_server_url (str): The URL for the PG server.

        Returns:
        - VectorStore: The Vector Store object.
        """

        try:
            vector_store = PGVector.from_existing_index(
                embedding=embedding,
                collection_name=collection_name,
                connection_string=pg_server_url,
            )

        except Exception as e:
            raise RuntimeError(f"Failed to build PGVector: {e}")
        return self.search_with_vector_store(
            input_value=input_value, search_type=search_type, vector_store=vector_store
        )

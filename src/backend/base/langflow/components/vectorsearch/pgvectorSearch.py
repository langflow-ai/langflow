from typing import List

from langchain.embeddings.base import Embeddings

from langflow.components.vectorstores.base.model import LCVectorStoreComponent
from langflow.components.vectorstores.pgvector import PGVectorComponent
from langflow.field_typing import Text
from langflow.schema import Record


class PGVectorSearchComponent(PGVectorComponent, LCVectorStoreComponent):
    display_name: str = "PGVector Search"
    description: str = "Search a PGVector Store for similar documents."
    documentation = "https://python.langchain.com/docs/integrations/vectorstores/pgvector"

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
        search_type: str,
        pg_server_url: str,
        collection_name: str,
        number_of_results: int = 4,
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
            vector_store = super().build(
                embedding=embedding,
                pg_server_url=pg_server_url,
                collection_name=collection_name,
            )
        except Exception as e:
            raise RuntimeError(f"Failed to build PGVector: {e}")
        return self.search_with_vector_store(
            input_value=input_value, search_type=search_type, vector_store=vector_store, k=number_of_results
        )

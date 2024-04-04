from typing import List, Optional

from langchain.embeddings.base import Embeddings

from langflow.components.vectorstores.base.model import LCVectorStoreComponent
from langflow.components.vectorstores.Redis import RedisComponent
from langflow.field_typing import Text
from langflow.schema import Record


class RedisSearchComponent(RedisComponent, LCVectorStoreComponent):
    """
    A custom component for implementing a Vector Store using Redis.
    """

    display_name: str = "Redis Search"
    description: str = "Search a Redis Vector Store for similar documents."
    documentation = "https://python.langchain.com/docs/integrations/vectorstores/redis"

    def build_config(self):
        """
        Builds the configuration for the component.

        Returns:
        - dict: A dictionary containing the configuration options for the component.
        """
        return {
            "search_type": {
                "display_name": "Search Type",
                "options": ["Similarity", "MMR"],
            },
            "input_value": {"display_name": "Input"},
            "index_name": {"display_name": "Index Name", "value": "your_index"},
            "code": {"show": False, "display_name": "Code"},
            "embedding": {"display_name": "Embedding"},
            "schema": {"display_name": "Schema", "file_types": [".yaml"]},
            "redis_server_url": {
                "display_name": "Redis Server Connection String",
                "advanced": False,
            },
            "redis_index_name": {"display_name": "Redis Index", "advanced": False},
            "number_of_results": {
                "display_name": "Number of Results",
                "info": "Number of results to return.",
                "advanced": True,
            },
        }

    def build(  # type: ignore[override]
        self,
        input_value: Text,
        search_type: str,
        embedding: Embeddings,
        redis_server_url: str,
        redis_index_name: str,
        number_of_results: int = 4,
        schema: Optional[str] = None,
    ) -> List[Record]:
        """
        Builds the Vector Store or BaseRetriever object.

        Args:
        - embedding (Embeddings): The embeddings to use for the Vector Store.
        - documents (Optional[Document]): The documents to use for the Vector Store.
        - redis_index_name (str): The name of the Redis index.
        - redis_server_url (str): The URL for the Redis server.

        Returns:
        - VectorStore: The Vector Store object.
        """
        vector_store = super().build(
            embedding=embedding,
            redis_server_url=redis_server_url,
            redis_index_name=redis_index_name,
            schema=schema,
        )
        if not vector_store:
            raise ValueError("Failed to load the Redis index.")

        return self.search_with_vector_store(
            input_value=input_value, search_type=search_type, vector_store=vector_store, k=number_of_results
        )

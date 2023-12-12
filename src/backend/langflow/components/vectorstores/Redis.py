from typing import Optional
from langflow import CustomComponent

from langchain.vectorstores.redis import Redis
from langchain.schema import Document
from langchain.vectorstores.base import VectorStore
from langchain.embeddings.base import Embeddings


class RedisComponent(CustomComponent):
    """
    A custom component for implementing a Vector Store using Redis.
    """

    display_name: str = "Redis"
    description: str = "Implementation of Vector Store using Redis"
    documentation = "https://python.langchain.com/docs/integrations/vectorstores/redis"
    beta = True

    def build_config(self):
        """
        Builds the configuration for the component.

        Returns:
        - dict: A dictionary containing the configuration options for the component.
        """
        return {
            "index_name": {"display_name": "Index Name", "value": "your_index"},
            "code": {"show": False, "display_name": "Code"},
            "documents": {"display_name": "Documents", "is_list": True},
            "embedding": {"display_name": "Embedding"},
            "redis_server_url": {
                "display_name": "Redis Server Connection String",
                "advanced": False,
            },
            "redis_index_name": {"display_name": "Redis Index", "advanced": False},
        }

    def build(
        self,
        embedding: Embeddings,
        redis_server_url: str,
        redis_index_name: str,
        documents: Optional[Document] = None,
    ) -> VectorStore:
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

        return Redis.from_documents(
            documents=documents,  # type: ignore
            embedding=embedding,
            redis_url=redis_server_url,
            index_name=redis_index_name,
        )

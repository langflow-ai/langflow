from typing import Optional, Union

from langchain_community.vectorstores.redis import Redis
from langchain_core.embeddings import Embeddings
from langchain_core.retrievers import BaseRetriever
from langchain_core.vectorstores import VectorStore

from langflow.custom import CustomComponent
from langflow.schema import Record


class RedisComponent(CustomComponent):
    """
    A custom component for implementing a Vector Store using Redis.
    """

    display_name: str = "Redis"
    description: str = "Implementation of Vector Store using Redis"
    documentation = "https://python.langchain.com/docs/integrations/vectorstores/redis"

    def build_config(self):
        """
        Builds the configuration for the component.

        Returns:
        - dict: A dictionary containing the configuration options for the component.
        """
        return {
            "index_name": {"display_name": "Index Name", "value": "your_index"},
            "code": {"show": False, "display_name": "Code"},
            "inputs": {"display_name": "Input", "input_types": ["Document", "Record"]},
            "embedding": {"display_name": "Embedding"},
            "schema": {"display_name": "Schema", "file_types": [".yaml"]},
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
        schema: Optional[str] = None,
        inputs: Optional[Record] = None,
    ) -> Union[VectorStore, BaseRetriever]:
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
        documents = []
        for _input in inputs or []:
            if isinstance(_input, Record):
                documents.append(_input.to_lc_document())
            else:
                documents.append(_input)
        if not documents:
            if schema is None:
                raise ValueError("If no documents are provided, a schema must be provided.")
            redis_vs = Redis.from_existing_index(
                embedding=embedding,
                index_name=redis_index_name,
                schema=schema,
                key_prefix=None,
                redis_url=redis_server_url,
            )
        else:
            redis_vs = Redis.from_documents(
                documents=documents,  # type: ignore
                embedding=embedding,
                redis_url=redis_server_url,
                index_name=redis_index_name,
            )
        return redis_vs

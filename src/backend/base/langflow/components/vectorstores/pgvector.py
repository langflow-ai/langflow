from typing import Optional, Union

from langchain_community.vectorstores.pgvector import PGVector
from langchain_core.embeddings import Embeddings
from langchain_core.retrievers import BaseRetriever
from langchain_core.vectorstores import VectorStore

from langflow.custom import CustomComponent
from langflow.schema import Record


class PGVectorComponent(CustomComponent):
    """
    A custom component for implementing a Vector Store using PostgreSQL.
    """

    display_name: str = "PGVector"
    description: str = "Implementation of Vector Store using PostgreSQL"
    documentation = "https://python.langchain.com/docs/integrations/vectorstores/pgvector"

    def build_config(self):
        """
        Builds the configuration for the component.

        Returns:
        - dict: A dictionary containing the configuration options for the component.
        """
        return {
            "code": {"show": False},
            "inputs": {"display_name": "Input", "input_types": ["Document", "Record"]},
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
        inputs: Optional[Record] = None,
    ) -> Union[VectorStore, BaseRetriever]:
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

        documents = []
        for _input in inputs or []:
            if isinstance(_input, Record):
                documents.append(_input.to_lc_document())
            else:
                documents.append(_input)
        try:
            if documents is None:
                vector_store = PGVector.from_existing_index(
                    embedding=embedding,
                    collection_name=collection_name,
                    connection_string=pg_server_url,
                )
            else:
                vector_store = PGVector.from_documents(
                    embedding=embedding,
                    documents=documents,  # type: ignore
                    collection_name=collection_name,
                    connection_string=pg_server_url,
                )
        except Exception as e:
            raise RuntimeError(f"Failed to build PGVector: {e}")
        return vector_store

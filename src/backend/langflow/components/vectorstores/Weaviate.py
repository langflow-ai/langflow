from typing import Optional, Union
from langflow import CustomComponent
from langchain.schema import Document
from langchain.vectorstores.base import VectorStore
from langchain.schema import BaseRetriever
from langchain.embeddings.base import Embeddings
import weaviate


class WeaviateComponent(CustomComponent):
    display_name = "Weaviate (Custom Component)"
    description = "Stores embeddings in Weaviate vector database"
    documentation = (
        "https://python.langchain.com/docs/integrations/vectorstores/weaviate"
    )
    beta = True

    def build_config(self):
        """
        Builds the configuration for the component.
        Returns:
        - dict: A dictionary containing the configuration options for the component.
        """
        return {
            "weaviate_api_key": {"display_name": "Weaviate API Key", "value": ""},
            "weaviate_url": {
                "display_name": "Weaviate Server URL",
                "value": "http://localhost:8080",
            },
            "documents": {"display_name": "Documents", "is_list": True},
            "embeddings": {"display_name": "Embedding"},
        }

    def build(
        self,
        weaviate_api_key: str,
        weaviate_url: str,
        documents: Optional[Document] = None,
        embeddings: Optional[Embeddings] = None,
    ) -> Union[VectorStore, BaseRetriever]:
        """
        Builds the Vector Store.
        Args:
        - weaviate_api_key: api used to authenticate with
        - weaviate_url: url of the server
        - embedding (Optional[Embeddings]): The embeddings to use for the Vector Store.
        - documents (Optional[Document]): The documents to use for the Vector Store.
        Returns:
        - Union[VectorStore, BaseRetriever]: The Vector Store or BaseRetriever object.
        """

        # Initialize Weaviate client with API key and URL
        client = weaviate.Client(weaviate_url, api_key=weaviate_api_key)

        # Store the embeddings in Weaviate
        references = []
        for embedding in embeddings:
            ref = client.data_object.create(
                {"vector": embedding.vector}
            )  # Placeholder method
            references.append(ref)

        return VectorStore(references=references)

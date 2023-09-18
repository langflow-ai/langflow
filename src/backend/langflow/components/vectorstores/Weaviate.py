from typing import List, Optional, Union
from langflow import CustomComponent
from langchain.schema import Document
from langchain.vectorstores.weaviate import Weaviate
from langchain.schema import BaseRetriever
from langchain.vectorstores.base import VectorStore
from langchain.embeddings.base import Embeddings
import weaviate  # type: ignore


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
            "client_kwargs": {
                "display_name": "Client Arguments",
                "advanced": True,
                "info": "Additional keyword arguments to pass to the Weaviate client.",
                "field_type": "code",
            },
        }

    def build(
        self,
        weaviate_api_key: str,
        weaviate_url: str,
        index_name: str,
        embeddings: Embeddings,
        text_key: str = "text",
        by_text: bool = True,
        documents: Optional[List[Document]] = None,
        attributes: List[str] = [],
        client_kwargs: Optional[dict] = None,
    ) -> Union[VectorStore, BaseRetriever]:
        # Initialize Weaviate client with API key and URL
        try:
            client = weaviate.Client(
                url=weaviate_url, api_key=weaviate_api_key, **client_kwargs
            )
        except Exception as exc:
            raise ValueError(f"Error initializing Weaviate client: {exc}") from exc
        # If documents are not provided, return a Weaviate instance
        if not documents:
            weaviate_client = weaviate.Client(weaviate_url, api_key=weaviate_api_key)

            return Weaviate(
                client=weaviate_client,
                index_name=index_name,
                text_key=text_key,
                by_text=by_text,
                attributes=attributes,
                embedding=embeddings,
            )
        # If documents are provided, return a Weaviate instance with documents
        return Weaviate.from_documents(
            client=client,
            documents=documents,
            embedding=embeddings,
            index_name=index_name,
            text_key=text_key,
            attributes=attributes,
            by_text=by_text,
        )

from typing import Optional, Union
from langflow import CustomComponent

from langchain.vectorstores import Pinecone
from langchain.vectorstores.base import VectorStore
from langchain.schema import BaseRetriever
from langchain.schema import Document
from langchain.embeddings.base import Embeddings
import pinecone  # type: ignore


class PineconeComponent(CustomComponent):
    """
    A custom component for implementing a Vector Store using Pinecone.
    """

    display_name: str = "Pinecone (Custom Component)"
    description: str = "Implementation of Vector Store using Pinecone"
    documentation = (
        "https://python.langchain.com/docs/integrations/vectorstores/pinecone"
    )
    beta = True

    def build_config(self):
        return {
            "api_key": {
                "display_name": "API Key",
                "password": True,
            },
            "environment": {"display_name": "Environment"},
            "index_name": {"display_name": "Index Name"},
            "documents": {"display_name": "Documents", "is_list": True},
            "namespace": {
                "display_name": "Namespace",
            },
            "embeddings": {"display_name": "Embeddings"},
            "code": {"display_name": "Code", "show": False},
        }

    def build(
        self,
        api_key: str,
        environment: str,
        index_name: str,
        documents: Optional[Document],
        embeddings: Optional[Embeddings],
    ) -> Union[VectorStore, BaseRetriever]:
        pinecone.init(
            api_key=api_key,  # find at app.pinecone.io
            environment=environment,  # next to api key in console
        )

        # First, check if our index already exists. If it doesn't, we create it
        if index_name not in pinecone.list_indexes():
            # we create a new index
            pinecone.create_index(name=index_name, metric="cosine", dimension=1536)

        if documents is not None and embeddings is not None:
            return Pinecone.from_documents(
                documents=documents,
                embedding=embeddings,
                index_name=index_name,
            )

        # if documents is None assume you already have an index and try to load it like this
        return Pinecone.from_existing_index(index_name=index_name, embedding=embeddings)

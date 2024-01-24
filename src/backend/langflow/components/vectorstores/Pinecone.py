from langflow import CustomComponent
from typing import Optional, List, Union
from langchain_community.vectorstores.pinecone import Pinecone
from langflow.field_typing import (
    Document,
    Embeddings,
)
from langchain.schema import BaseRetriever
from langchain.vectorstores.base import VectorStore
import pinecone


class PineconeComponent(CustomComponent):
    display_name = "Pinecone"
    description = "Construct Pinecone wrapper from raw documents."

    def build_config(self):
        return {
            "documents": {"display_name": "Documents"},
            "embedding": {"display_name": "Embedding", "default": 1000},
            "index_name": {"display_name": "Index Name"},
            "namespace": {"display_name": "Namespace"},
            "pinecone_api_key": {"display_name": "Pinecone API Key", "default": "", "password": True, "required": True},
            "pinecone_env": {"display_name": "Pinecone Environment", "default": "", "required": True},
            "search_kwargs": {"display_name": "Search Kwargs", "default": "{}"},
        }

    def build(
        self,
        embedding: Embeddings,
        documents: Optional[List[Document]] = None,
        index_name: Optional[str] = None,
        pinecone_api_key: Optional[str] = None,
        pinecone_env: Optional[str] = None,
    ) -> Union[VectorStore, Pinecone, BaseRetriever]:
        pinecone.init(api_key=pinecone_api_key, environment=pinecone_env)
        return Pinecone.from_documents(documents=documents, embedding=embedding, index_name=index_name)

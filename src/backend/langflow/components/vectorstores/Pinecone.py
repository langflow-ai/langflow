
from langflow import CustomComponent
from typing import Optional, List
from langchain.vectorstores import Pinecone
from langchain.field_typing import (
    Document,
    Embeddings,
    NestedDict,
)

class PineconeComponent(CustomComponent):
    display_name = "Pinecone"
    description = "Construct Pinecone wrapper from raw documents."

    def build_config(self):
        return {
            "documents": {"display_name": "Documents"},
            "embedding": {"display_name": "Embedding", "default": 1000},
            "index_name": {"display_name": "Index Name"},
            "namespace": {"display_name": "Namespace"},
            "pinecone_api_key": {"display_name": "Pinecone API Key", "default": ""},
            "pinecone_env": {"display_name": "Pinecone Environment", "default": ""},
            "search_kwargs": {"display_name": "Search Kwargs", "default": '{}'},
        }

    def build(
        self,
        embedding: Embeddings,
        documents: Optional[List[Document]] = None,
        index_name: Optional[str] = None,
        namespace: Optional[str] = None,
        pinecone_api_key: Optional[str] = None,
        pinecone_env: Optional[str] = None,
        search_kwargs: Optional[NestedDict] = None,
    ) -> Pinecone:
        return Pinecone(
            documents=documents,
            embedding=embedding,
            index_name=index_name,
            namespace=namespace,
            pinecone_api_key=pinecone_api_key,
            pinecone_env=pinecone_env,
            search_kwargs=search_kwargs,
        )

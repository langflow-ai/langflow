import os
from typing import List, Optional, Union

import pinecone  # type: ignore
from langchain.schema import BaseRetriever
from langchain_community.vectorstores import VectorStore
from langchain_community.vectorstores.pinecone import Pinecone

from langflow import CustomComponent
from langflow.field_typing import Document, Embeddings


class PineconeComponent(CustomComponent):
    display_name = "Pinecone"
    description = "Construct Pinecone wrapper from raw documents."

    def build_config(self):
        return {
            "documents": {"display_name": "Documents"},
            "embedding": {"display_name": "Embedding"},
            "index_name": {"display_name": "Index Name"},
            "namespace": {"display_name": "Namespace"},
            "pinecone_api_key": {"display_name": "Pinecone API Key", "default": "", "password": True, "required": True},
            "pinecone_env": {"display_name": "Pinecone Environment", "default": "", "required": True},
            "search_kwargs": {"display_name": "Search Kwargs", "default": "{}"},
            "pool_threads": {"display_name": "Pool Threads", "default": 1, "advanced": True},
        }

    def build(
        self,
        embedding: Embeddings,
        pinecone_env: str,
        documents: List[Document],
        index_name: Optional[str] = None,
        pinecone_api_key: Optional[str] = None,
        text_key: Optional[str] = "text",
        namespace: Optional[str] = "default",
        pool_threads: Optional[int] = None,
    ) -> Union[VectorStore, Pinecone, BaseRetriever]:
        if pinecone_api_key is None or pinecone_env is None:
            raise ValueError("Pinecone API Key and Environment are required.")
        if os.getenv("PINECONE_API_KEY") is None and pinecone_api_key is None:
            raise ValueError("Pinecone API Key is required.")

        pinecone.init(api_key=pinecone_api_key, environment=pinecone_env)  # type: ignore
        if documents:
            return Pinecone.from_documents(
                documents=documents,
                embedding=embedding,
                index_name=index_name,
                pool_threads=pool_threads,
                namespace=namespace,
                text_key=text_key,
            )

        return Pinecone.from_existing_index(
            index_name=index_name,
            embedding=embedding,
            text_key=text_key,
            namespace=namespace,
            pool_threads=pool_threads,
        )

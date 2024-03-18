import os
from typing import List, Optional, Union

import pinecone  # type: ignore
from langchain.schema import BaseRetriever
from langchain_community.vectorstores import VectorStore
from langchain_community.vectorstores.pinecone import Pinecone

from langflow import CustomComponent
from langflow.field_typing import Embeddings
from langflow.schema.schema import Record


class PineconeComponent(CustomComponent):
    display_name = "Pinecone"
    description = "Construct Pinecone wrapper from raw documents."
    icon = "Pinecone"

    def build_config(self):
        return {
            "inputs": {"display_name": "Input", "input_types": ["Document", "Record"]},
            "embedding": {"display_name": "Embedding"},
            "index_name": {"display_name": "Index Name"},
            "namespace": {"display_name": "Namespace"},
            "pinecone_api_key": {
                "display_name": "Pinecone API Key",
                "default": "",
                "password": True,
                "required": True,
            },
            "pinecone_env": {
                "display_name": "Pinecone Environment",
                "default": "",
                "required": True,
            },
            "search_kwargs": {"display_name": "Search Kwargs", "default": "{}"},
            "pool_threads": {
                "display_name": "Pool Threads",
                "default": 1,
                "advanced": True,
            },
        }

    def build(
        self,
        embedding: Embeddings,
        pinecone_env: str,
        inputs: Optional[List[Record]] = None,
        text_key: str = "text",
        pool_threads: int = 4,
        index_name: Optional[str] = None,
        pinecone_api_key: Optional[str] = None,
        namespace: Optional[str] = "default",
    ) -> Union[VectorStore, Pinecone, BaseRetriever]:
        if pinecone_api_key is None or pinecone_env is None:
            raise ValueError("Pinecone API Key and Environment are required.")
        if os.getenv("PINECONE_API_KEY") is None and pinecone_api_key is None:
            raise ValueError("Pinecone API Key is required.")

        pinecone.init(api_key=pinecone_api_key, environment=pinecone_env)  # type: ignore
        if not index_name:
            raise ValueError("Index Name is required.")
        documents = []
        for _input in inputs or []:
            if isinstance(_input, Record):
                documents.append(_input.to_lc_document())
            else:
                documents.append(_input)
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

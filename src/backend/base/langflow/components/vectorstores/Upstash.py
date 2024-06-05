from typing import List, Optional, Union

from langchain_community.vectorstores.upstash import UpstashVectorStore
from langchain_core.embeddings import Embeddings
from langchain_core.retrievers import BaseRetriever
from langchain_core.vectorstores import VectorStore

from langflow.custom import CustomComponent
from langflow.schema.schema import Record


class UpstashVectorStoreComponent(CustomComponent):
    """
    A custom component for implementing a Vector Store using Upstash.
    """

    display_name: str = "Upstash"
    description: str = "Create and Utilize an Upstash Vector Store"

    def build_config(self):
        """
        Builds the configuration for the component.

        Returns:
        - dict: A dictionary containing the configuration options for the component.
        """
        return {
            "inputs": {"display_name": "Input", "input_types": ["Document", "Record"]},
            "embedding": {
                "display_name": "Embedding",
                "input_types": ["Embeddings"],
                "info": "To use Upstash's embeddings, don't provide an embedding.",
            },
            "index_url": {
                "display_name": "Index URL",
                "info": "The URL of the Upstash index.",
            },
            "index_token": {
                "display_name": "Index Token",
                "info": "The token for the Upstash index.",
            },
            "text_key": {
                "display_name": "Text Key",
                "info": "The key in the record to use as text.",
                "advanced": True,
            },
        }

    def build(
        self,
        inputs: Optional[List[Record]] = None,
        text_key: str = "text",
        index_url: Optional[str] = None,
        index_token: Optional[str] = None,
        embedding: Optional[Embeddings] = None,
    ) -> Union[VectorStore, BaseRetriever]:
        documents = []
        for _input in inputs or []:
            if isinstance(_input, Record):
                documents.append(_input.to_lc_document())
            else:
                documents.append(_input)

        use_upstash_embedding = embedding is None
        if not documents:
            upstash_vs = UpstashVectorStore(
                embedding=embedding or use_upstash_embedding,
                text_key=text_key,
                index_url=index_url,
                index_token=index_token,
            )
        else:
            if use_upstash_embedding:
                upstash_vs = UpstashVectorStore(
                    embedding=use_upstash_embedding,
                    text_key=text_key,
                    index_url=index_url,
                    index_token=index_token,
                )
                upstash_vs.add_documents(documents)
            elif embedding:
                upstash_vs = UpstashVectorStore.from_documents(
                    documents=documents,  # type: ignore
                    embedding=embedding,
                    text_key=text_key,
                    index_url=index_url,
                    index_token=index_token,
                )
        return upstash_vs

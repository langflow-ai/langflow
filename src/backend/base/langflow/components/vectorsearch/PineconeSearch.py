from typing import List, Optional

from langflow.components.vectorstores.base.model import LCVectorStoreComponent
from langflow.components.vectorstores.Pinecone import PineconeComponent
from langflow.field_typing import Embeddings, Text
from langflow.schema import Record


class PineconeSearchComponent(PineconeComponent, LCVectorStoreComponent):
    display_name = "Pinecone Search"
    description = "Search a Pinecone Vector Store for similar documents."
    icon = "Pinecone"

    def build_config(self):
        return {
            "search_type": {
                "display_name": "Search Type",
                "options": ["Similarity", "MMR"],
            },
            "input_value": {"display_name": "Input"},
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

    def build(  # type: ignore[override]
        self,
        input_value: Text,
        embedding: Embeddings,
        pinecone_env: str,
        text_key: str = "text",
        pool_threads: int = 4,
        index_name: Optional[str] = None,
        pinecone_api_key: Optional[str] = None,
        namespace: Optional[str] = "default",
        search_type: str = "similarity",
    ) -> List[Record]:  # type: ignore[override]
        vector_store = super().build(
            embedding=embedding,
            pinecone_env=pinecone_env,
            inputs=[],
            text_key=text_key,
            pool_threads=pool_threads,
            index_name=index_name,
            pinecone_api_key=pinecone_api_key,
            namespace=namespace,
        )
        if not vector_store:
            raise ValueError("Failed to load the Pinecone index.")

        return self.search_with_vector_store(
            vector_store=vector_store, input_value=input_value, search_type=search_type
        )

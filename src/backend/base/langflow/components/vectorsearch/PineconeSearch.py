from typing import List, Optional

from langchain_pinecone._utilities import DistanceStrategy

from langflow.components.vectorstores.base.model import LCVectorStoreComponent
from langflow.components.vectorstores.Pinecone import PineconeComponent
from langflow.field_typing import Embeddings, Text
from langflow.field_typing.constants import NestedDict
from langflow.schema import Record


class PineconeSearchComponent(PineconeComponent, LCVectorStoreComponent):
    display_name = "Pinecone Search"
    description = "Search a Pinecone Vector Store for similar documents."
    icon = "Pinecone"
    field_order = ["index_name", "namespace", "distance_strategy", "pinecone_api_key", "input_value", "embedding"]

    def build_config(self):
        distance_options = [e.value.title().replace("_", " ") for e in DistanceStrategy]
        distance_value = distance_options[0]
        return {
            "search_type": {
                "display_name": "Search Type",
                "options": ["Similarity", "MMR"],
            },
            "input_value": {"display_name": "Input"},
            "embedding": {"display_name": "Embedding"},
            "index_name": {"display_name": "Index Name"},
            "namespace": {"display_name": "Namespace", "advanced": True},
            "distance_strategy": {
                "display_name": "Distance Strategy",
                # get values from enum
                # and make them title case for display
                "options": distance_options,
                "advanced": True,
                "value": distance_value,
            },
            "pinecone_api_key": {
                "display_name": "Pinecone API Key",
                "default": "",
                "password": True,
            },
            "pool_threads": {
                "display_name": "Pool Threads",
                "default": 1,
                "advanced": True,
            },
            "number_of_results": {
                "display_name": "Number of Results",
                "info": "Number of results to return.",
                "advanced": True,
            },
            "text_key": {
                "display_name": "Text Key",
                "info": "Key in the record to use as text.",
                "advanced": True,
            },
        }

    def build(  # type: ignore[override]
        self,
        input_value: Text,
        embedding: Embeddings,
        distance_strategy: str,
        text_key: str = "text",
        number_of_results: int = 4,
        pool_threads: int = 4,
        index_name: Optional[str] = None,
        pinecone_api_key: Optional[str] = None,
        namespace: Optional[str] = "default",
        search_type: str = "similarity",
        search_kwargs: Optional[NestedDict] = None,
    ) -> List[Record]:  # type: ignore[override]
        vector_store = super().build(
            embedding=embedding,
            distance_strategy=distance_strategy,
            inputs=[],
            text_key=text_key,
            pool_threads=pool_threads,
            index_name=index_name,
            pinecone_api_key=pinecone_api_key,
            namespace=namespace,
        )
        if not vector_store:
            raise ValueError("Failed to load the Pinecone index.")
        if search_kwargs is None:
            search_kwargs = {}

        return self.search_with_vector_store(
            vector_store=vector_store,
            input_value=input_value,
            search_type=search_type,
            k=number_of_results,
            **search_kwargs,
        )

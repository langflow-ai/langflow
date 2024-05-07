from typing import List, Optional, Union

from langchain.schema import BaseRetriever
from langchain_community.vectorstores import VectorStore
from langchain_pinecone._utilities import DistanceStrategy
from langchain_pinecone.vectorstores import PineconeVectorStore

from langflow.field_typing import Embeddings
from langflow.interface.custom.custom_component import CustomComponent
from langflow.schema.schema import Record


class PineconeComponent(CustomComponent):
    display_name = "Pinecone"
    description = "Construct Pinecone wrapper from raw documents."
    icon = "Pinecone"

    def build_config(self):
        distance_options = [e.value.title().replace("_", " ") for e in DistanceStrategy]
        distance_value = distance_options[0]
        return {
            "inputs": {"display_name": "Input", "input_types": ["Document", "Record"]},
            "embedding": {"display_name": "Embedding"},
            "index_name": {"display_name": "Index Name"},
            "namespace": {"display_name": "Namespace"},
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
                "required": True,
            },
            "pool_threads": {
                "display_name": "Pool Threads",
                "default": 1,
                "advanced": True,
            },
        }

    def build(
        self,
        embedding: Embeddings,
        inputs: Optional[List[Record]] = None,
        text_key: str = "text",
        pool_threads: int = 4,
        index_name: Optional[str] = None,
        pinecone_api_key: Optional[str] = None,
        distance_strategy: Optional[DistanceStrategy] = None,
        namespace: Optional[str] = "default",
    ) -> Union[VectorStore, BaseRetriever]:
        # get distance strategy from string
        distance_strategy = distance_strategy.replace(" ", "_").upper()
        _distance_strategy = DistanceStrategy[distance_strategy]
        if not index_name:
            raise ValueError("Index Name is required.")
        documents = []
        for _input in inputs or []:
            if isinstance(_input, Record):
                documents.append(_input.to_lc_document())
            else:
                documents.append(_input)
        if documents:
            return PineconeVectorStore.from_documents(
                documents=documents,
                embedding=embedding,
                index_name=index_name,
                pool_threads=pool_threads,
                namespace=namespace,
                text_key=text_key,
                pinecone_api_key=pinecone_api_key,
                distance_strategy=_distance_strategy,
            )

        return PineconeVectorStore.from_existing_index(
            index_name=index_name,
            embedding=embedding,
            text_key=text_key,
            namespace=namespace,
            pool_threads=pool_threads,
        )

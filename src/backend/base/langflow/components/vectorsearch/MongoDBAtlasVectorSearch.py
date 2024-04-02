from typing import List, Optional

from langflow.components.vectorstores.base.model import LCVectorStoreComponent
from langflow.components.vectorstores.MongoDBAtlasVector import MongoDBAtlasComponent
from langflow.field_typing import Embeddings, NestedDict, Text
from langflow.schema import Record


class MongoDBAtlasSearchComponent(LCVectorStoreComponent):
    display_name = "MongoDB Atlas Search"
    description = "Search a MongoDB Atlas Vector Store for similar documents."

    def build_config(self):
        return {
            "search_type": {
                "display_name": "Search Type",
                "options": ["Similarity", "MMR"],
            },
            "input_value": {"display_name": "Input"},
            "embedding": {"display_name": "Embedding"},
            "collection_name": {"display_name": "Collection Name"},
            "db_name": {"display_name": "Database Name"},
            "index_name": {"display_name": "Index Name"},
            "mongodb_atlas_cluster_uri": {"display_name": "MongoDB Atlas Cluster URI"},
            "search_kwargs": {"display_name": "Search Kwargs", "advanced": True},
            "number_of_results": {
                "display_name": "Number of Results",
                "info": "Number of results to return.",
                "advanced": True,
            },
        }

    def build(  # type: ignore[override]
        self,
        input_value: Text,
        search_type: str,
        embedding: Embeddings,
        number_of_results: int = 4,
        collection_name: str = "",
        db_name: str = "",
        index_name: str = "",
        mongodb_atlas_cluster_uri: str = "",
        search_kwargs: Optional[NestedDict] = None,
    ) -> List[Record]:
        search_kwargs = search_kwargs or {}
        vector_store = MongoDBAtlasComponent().build(
            mongodb_atlas_cluster_uri=mongodb_atlas_cluster_uri,
            collection_name=collection_name,
            db_name=db_name,
            embedding=embedding,
            index_name=index_name,
        )
        if not vector_store:
            raise ValueError("Failed to create MongoDB Atlas Vector Store")
        return self.search_with_vector_store(
            vector_store=vector_store, input_value=input_value, search_type=search_type, k=number_of_results
        )

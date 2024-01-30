from typing import List, Optional

from langchain_community.vectorstores import MongoDBAtlasVectorSearch

from langflow import CustomComponent
from langflow.field_typing import (
    Document,
    Embeddings,
    NestedDict,
)


class MongoDBAtlasComponent(CustomComponent):
    display_name = "MongoDB Atlas"
    description = "Construct a `MongoDB Atlas Vector Search` vector store from raw documents."

    def build_config(self):
        return {
            "documents": {"display_name": "Documents"},
            "embedding": {"display_name": "Embedding"},
            "collection_name": {"display_name": "Collection Name"},
            "db_name": {"display_name": "Database Name"},
            "index_name": {"display_name": "Index Name"},
            "mongodb_atlas_cluster_uri": {"display_name": "MongoDB Atlas Cluster URI"},
            "search_kwargs": {"display_name": "Search Kwargs", "advanced": True},
        }

    def build(
        self,
        documents: List[Document],
        embedding: Embeddings,
        collection_name: str = "",
        db_name: str = "",
        index_name: str = "",
        mongodb_atlas_cluster_uri: str = "",
        search_kwargs: Optional[NestedDict] = None,
    ) -> MongoDBAtlasVectorSearch:
        search_kwargs = search_kwargs or {}
        return MongoDBAtlasVectorSearch(
            documents=documents,
            embedding=embedding,
            collection_name=collection_name,
            db_name=db_name,
            index_name=index_name,
            mongodb_atlas_cluster_uri=mongodb_atlas_cluster_uri,
            search_kwargs=search_kwargs,
        )

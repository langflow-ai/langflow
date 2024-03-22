from typing import List, Optional

from langchain_community.vectorstores.mongodb_atlas import MongoDBAtlasVectorSearch

from langflow import CustomComponent
from langflow.field_typing import Document, Embeddings, NestedDict


class MongoDBAtlasComponent(CustomComponent):
    display_name = "MongoDB Atlas"
    description = "a `MongoDB Atlas Vector Search` vector store from raw documents."

    def build_config(self):
        return {
            "documents": {"display_name": "Documents", "is_list": True},
            "embedding": {"display_name": "Embedding"},
            "collection_name": {"display_name": "Collection Name"},
            "db_name": {"display_name": "Database Name"},
            "index_name": {"display_name": "Index Name"},
            "mongodb_atlas_cluster_uri": {"display_name": "MongoDB Atlas Cluster URI"},
            "search_kwargs": {"display_name": "Search Kwargs", "advanced": True},
        }

    def build(
        self,
        embedding: Embeddings,
        documents: Optional[List[Document]] = None,
        collection_name: str = "",
        db_name: str = "",
        index_name: str = "",
        mongodb_atlas_cluster_uri: str = "",
        search_kwargs: Optional[NestedDict] = None,
    ) -> MongoDBAtlasVectorSearch:
        search_kwargs = search_kwargs or {}
        vector_store = MongoDBAtlasVectorSearch.from_connection_string(
            connection_string=mongodb_atlas_cluster_uri,
            namespace=f"{db_name}.{collection_name}",
            embedding=embedding,
            index_name=index_name,
        )

        if documents is not None:
            if len(documents) == 0:
                raise ValueError("If documents are provided, there must be at least one document.")

            vector_store.add_documents(documents)

        return vector_store

from typing import List, Optional

from langchain_community.vectorstores.mongodb_atlas import MongoDBAtlasVectorSearch
from langflow.field_typing import Embeddings
from langflow.interface.custom.custom_component import CustomComponent
from langflow.schema.schema import Record


class MongoDBAtlasComponent(CustomComponent):
    display_name = "MongoDB Atlas"
    description = "Construct a `MongoDB Atlas Vector Search` vector store from raw documents."
    icon = "MongoDB"

    def build_config(self):
        return {
            "inputs": {"display_name": "Input", "input_types": ["Document", "Record"]},
            "embedding": {"display_name": "Embedding"},
            "collection_name": {"display_name": "Collection Name"},
            "db_name": {"display_name": "Database Name"},
            "index_name": {"display_name": "Index Name"},
            "mongodb_atlas_cluster_uri": {"display_name": "MongoDB Atlas Cluster URI"},
        }

    def build(
        self,
        embedding: Embeddings,
        inputs: Optional[List[Record]] = None,
        collection_name: str = "",
        db_name: str = "",
        index_name: str = "",
        mongodb_atlas_cluster_uri: str = "",
    ) -> MongoDBAtlasVectorSearch:
        try:
            from pymongo import MongoClient
        except ImportError:
            raise ImportError("Please install pymongo to use MongoDB Atlas Vector Store")
        try:
            mongo_client: MongoClient = MongoClient(mongodb_atlas_cluster_uri)
            collection = mongo_client[db_name][collection_name]
        except Exception as e:
            raise ValueError(f"Failed to connect to MongoDB Atlas: {e}")
        documents = []
        for _input in inputs or []:
            if isinstance(_input, Record):
                documents.append(_input.to_lc_document())
            else:
                documents.append(_input)
        if documents:
            vector_store = MongoDBAtlasVectorSearch.from_documents(
                documents=documents,
                embedding=embedding,
                collection=collection,
                db_name=db_name,
                index_name=index_name,
                mongodb_atlas_cluster_uri=mongodb_atlas_cluster_uri,
            )
        else:
            vector_store = MongoDBAtlasVectorSearch(
                embedding=embedding,
                collection=collection,
                index_name=index_name,
            )
        return vector_store

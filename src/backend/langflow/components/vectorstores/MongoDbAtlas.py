from typing import Optional
from langflow import CustomComponent

from langchain.vectorstores import MongoDBAtlasVectorSearch
from langchain.schema import Document
from langchain.embeddings.base import Embeddings


class MongoDbAtlasComponent(CustomComponent):
    """
    A custom component for implementing a Vector Store using MongoDb Atlas.
    """

    display_name: str = "MongoDb Atlas (Custom Component)"
    description: str = "Implementation of Vector Store using MongoDb Atlas"
    documentation = (
        "https://python.langchain.com/docs/integrations/vectorstores/mongodb_atlas"
    )
    beta = True

    def build_config(self):
        return {
            "collection_name": {"display_name": "Collection Name", "value": "langflow"},
            "mongodb_atlas_cluster_uri": {
                "display_name": "Atlas Cluster Uri",
                "password": True,
            },
            "db_name": {"display_name": "Database Name", "value": "langflow"},
            "index_name": {"display_name": "Index Name", "required": False},
            "code": {"display_name": "Code", "show": False},
            "documents": {"display_name": "Documents", "is_list": True},
            "embedding": {"display_name": "Embedding"},
        }

    def build(
        self,
        collection_name: str,
        mongodb_atlas_cluster_uri: str,
        db_name: str,
        index_name: Optional[str] = None,
        documents: Optional[Document] = None,
        embeddings: Optional[Embeddings] = None,
    ) -> MongoDBAtlasVectorSearch:
        if not mongodb_atlas_cluster_uri:
            raise ValueError("Mongodb atlas cluster uri must be provided in the params")
        from pymongo import MongoClient
        import certifi

        client: MongoClient = MongoClient(
            mongodb_atlas_cluster_uri, tlsCAFile=certifi.where()
        )
        if not db_name or not collection_name:
            raise ValueError(
                "db_name and collection_name must be provided in the params"
            )

        if not index_name:
            raise ValueError("index_name must be provided in the params")

        collection = client[db_name][collection_name]
        if not documents:
            return MongoDBAtlasVectorSearch(
                collection=collection, index_name=index_name, embedding=embeddings
            )

        return MongoDBAtlasVectorSearch.from_documents(
            collection=collection,
            embedding=embeddings,
            index_name=index_name,
            documents=documents,
        )

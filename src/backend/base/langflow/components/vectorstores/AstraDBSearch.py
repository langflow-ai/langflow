from typing import List, Optional

from langflow.components.vectorstores.AstraDB import AstraDBVectorStoreComponent
from langflow.components.vectorstores.base.model import LCVectorStoreComponent
from langflow.field_typing import Embeddings, Text
from langflow.schema import Record


class AstraDBSearchComponent(AstraDBVectorStoreComponent, LCVectorStoreComponent):
    display_name = "AstraDB Search"
    description = "Searches an existing AstraDB Vector Store"

    def build_config(self):
        return {
            "search_type": {
                "display_name": "Search Type",
                "options": ["Similarity", "MMR"],
            },
            "input_value": {
                "display_name": "Input Value",
                "info": "Input value to search",
            },
            "embedding": {"display_name": "Embedding", "info": "Embedding to use"},
            "collection_name": {"display_name": "Collection Name", "info": "Collection name"},
            "token": {"display_name": "Token", "info": "Token to use", "password": True},
            "api_endpoint": {"display_name": "API Endpoint", "info": "API Endpoint to use"},
            "namespace": {"display_name": "Namespace", "info": "Namespace to use", "advanced": True},
            "metric": {"display_name": "Metric", "info": "Metric to use", "advanced": True},
            "batch_size": {"display_name": "Batch Size", "info": "Batch size to use", "advanced": True},
            "bulk_insert_batch_concurrency": {
                "display_name": "Bulk Insert Batch Concurrency",
                "info": "Bulk Insert Batch Concurrency to use",
                "advanced": True,
            },
            "bulk_insert_overwrite_concurrency": {
                "display_name": "Bulk Insert Overwrite Concurrency",
                "info": "Bulk Insert Overwrite Concurrency to use",
                "advanced": True,
            },
            "bulk_delete_concurrency": {
                "display_name": "Bulk Delete Concurrency",
                "info": "Bulk Delete Concurrency to use",
                "advanced": True,
            },
            "setup_mode": {
                "display_name": "Setup Mode",
                "info": "Setup mode for the vector store",
                "options": ["Sync", "Async", "Off"],
                "advanced": True,
            },
            "pre_delete_collection": {
                "display_name": "Pre Delete Collection",
                "info": "Pre delete collection",
                "advanced": True,
            },
            "metadata_indexing_include": {
                "display_name": "Metadata Indexing Include",
                "info": "Metadata Indexing Include",
                "advanced": True,
            },
            "metadata_indexing_exclude": {
                "display_name": "Metadata Indexing Exclude",
                "info": "Metadata Indexing Exclude",
                "advanced": True,
            },
            "collection_indexing_policy": {
                "display_name": "Collection Indexing Policy",
                "info": "Collection Indexing Policy",
                "advanced": True,
            },
        }

    def build(
        self,
        embedding: Embeddings,
        collection_name: str,
        input_value: Optional[Text] = None,
        search_type: str = "Similarity",
        token: Optional[str] = None,
        api_endpoint: Optional[str] = None,
        namespace: Optional[str] = None,
        metric: Optional[str] = None,
        batch_size: Optional[int] = None,
        bulk_insert_batch_concurrency: Optional[int] = None,
        bulk_insert_overwrite_concurrency: Optional[int] = None,
        bulk_delete_concurrency: Optional[int] = None,
        setup_mode: str = "Sync",
        pre_delete_collection: bool = False,
        metadata_indexing_include: Optional[List[str]] = None,
        metadata_indexing_exclude: Optional[List[str]] = None,
        collection_indexing_policy: Optional[dict] = None,
    ) -> List[Record]:
        vector_store = super().build(
            embedding=embedding,
            collection_name=collection_name,
            token=token,
            api_endpoint=api_endpoint,
            namespace=namespace,
            metric=metric,
            batch_size=batch_size,
            bulk_insert_batch_concurrency=bulk_insert_batch_concurrency,
            bulk_insert_overwrite_concurrency=bulk_insert_overwrite_concurrency,
            bulk_delete_concurrency=bulk_delete_concurrency,
            setup_mode=setup_mode,
            pre_delete_collection=pre_delete_collection,
            metadata_indexing_include=metadata_indexing_include,
            metadata_indexing_exclude=metadata_indexing_exclude,
            collection_indexing_policy=collection_indexing_policy,
        )
        return self.search_with_vector_store(input_value, search_type, vector_store)

from typing import List, Optional

from langflow.components.vectorstores.AstraDB import AstraDBVectorStoreComponent
from langflow.components.vectorstores.base.model import LCVectorStoreComponent
from langflow.field_typing import Embeddings, Text
from langflow.schema import Record


class AstraDBSearchComponent(LCVectorStoreComponent):
    display_name = "Astra DB Search"
    description = "Searches an existing Astra DB Vector Store."
    icon = "AstraDB"
    field_order = ["token", "api_endpoint", "collection_name", "input_value", "embedding"]

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
            "collection_name": {
                "display_name": "Collection Name",
                "info": "The name of the collection within Astra DB where the vectors will be stored.",
            },
            "token": {
                "display_name": "Token",
                "info": "Authentication token for accessing Astra DB.",
                "password": True,
            },
            "api_endpoint": {
                "display_name": "API Endpoint",
                "info": "API endpoint URL for the Astra DB service.",
            },
            "namespace": {
                "display_name": "Namespace",
                "info": "Optional namespace within Astra DB to use for the collection.",
                "advanced": True,
            },
            "metric": {
                "display_name": "Metric",
                "info": "Optional distance metric for vector comparisons in the vector store.",
                "advanced": True,
            },
            "batch_size": {
                "display_name": "Batch Size",
                "info": "Optional number of records to process in a single batch.",
                "advanced": True,
            },
            "bulk_insert_batch_concurrency": {
                "display_name": "Bulk Insert Batch Concurrency",
                "info": "Optional concurrency level for bulk insert operations.",
                "advanced": True,
            },
            "bulk_insert_overwrite_concurrency": {
                "display_name": "Bulk Insert Overwrite Concurrency",
                "info": "Optional concurrency level for bulk insert operations that overwrite existing records.",
                "advanced": True,
            },
            "bulk_delete_concurrency": {
                "display_name": "Bulk Delete Concurrency",
                "info": "Optional concurrency level for bulk delete operations.",
                "advanced": True,
            },
            "setup_mode": {
                "display_name": "Setup Mode",
                "info": "Configuration mode for setting up the vector store, with options like “Sync”, “Async”, or “Off”.",
                "options": ["Sync", "Async", "Off"],
                "advanced": True,
            },
            "pre_delete_collection": {
                "display_name": "Pre Delete Collection",
                "info": "Boolean flag to determine whether to delete the collection before creating a new one.",
                "advanced": True,
            },
            "metadata_indexing_include": {
                "display_name": "Metadata Indexing Include",
                "info": "Optional list of metadata fields to include in the indexing.",
                "advanced": True,
            },
            "metadata_indexing_exclude": {
                "display_name": "Metadata Indexing Exclude",
                "info": "Optional list of metadata fields to exclude from the indexing.",
                "advanced": True,
            },
            "collection_indexing_policy": {
                "display_name": "Collection Indexing Policy",
                "info": "Optional dictionary defining the indexing policy for the collection.",
                "advanced": True,
            },
            "number_of_results": {
                "display_name": "Number of Results",
                "info": "Number of results to return.",
                "advanced": True,
            },
        }

    def build(
        self,
        embedding: Embeddings,
        collection_name: str,
        input_value: Text,
        token: str,
        api_endpoint: str,
        search_type: str = "Similarity",
        number_of_results: int = 4,
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
        vector_store = AstraDBVectorStoreComponent().build(
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
        try:
            return self.search_with_vector_store(input_value, search_type, vector_store, k=number_of_results)
        except KeyError as e:
            if "content" in str(e):
                raise ValueError(
                    "You should ingest data through Langflow (or LangChain) to query it in Langflow. Your collection does not contain a field name 'content'."
                )
            else:
                raise e

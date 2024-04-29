from typing import List, Optional, Union

from langchain.schema import BaseRetriever
from langchain_astradb import AstraDBVectorStore
from langchain_astradb.utils.astradb import SetupMode

from langflow.custom import CustomComponent
from langflow.field_typing import Embeddings, VectorStore
from langflow.schema import Record


class AstraDBVectorStoreComponent(CustomComponent):
    display_name = "Astra DB"
    description = "Builds or loads an Astra DB Vector Store."
    icon = "AstraDB"
    field_order = ["token", "api_endpoint", "collection_name", "inputs", "embedding"]

    def build_config(self):
        return {
            "inputs": {
                "display_name": "Inputs",
                "info": "Optional list of records to be processed and stored in the vector store.",
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
        }

    def build(
        self,
        embedding: Embeddings,
        token: str,
        api_endpoint: str,
        collection_name: str,
        inputs: Optional[List[Record]] = None,
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
    ) -> Union[VectorStore, BaseRetriever]:
        try:
            setup_mode_value = SetupMode[setup_mode.upper()]
        except KeyError:
            raise ValueError(f"Invalid setup mode: {setup_mode}")
        if inputs:
            documents = [_input.to_lc_document() for _input in inputs]

            vector_store = AstraDBVectorStore.from_documents(
                documents=documents,
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
                setup_mode=setup_mode_value,
                pre_delete_collection=pre_delete_collection,
                metadata_indexing_include=metadata_indexing_include,
                metadata_indexing_exclude=metadata_indexing_exclude,
                collection_indexing_policy=collection_indexing_policy,
            )
        else:
            vector_store = AstraDBVectorStore(
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
                setup_mode=setup_mode_value,
                pre_delete_collection=pre_delete_collection,
                metadata_indexing_include=metadata_indexing_include,
                metadata_indexing_exclude=metadata_indexing_exclude,
                collection_indexing_policy=collection_indexing_policy,
            )

        return vector_store

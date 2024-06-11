from datetime import timedelta
from typing import List, Optional, Union

from langchain_core.retrievers import BaseRetriever

from langflow.custom import CustomComponent
from langflow.field_typing import Embeddings, VectorStore
from langflow.schema import Record


class CouchbaseComponent(CustomComponent):
    display_name = "Couchbase"
    description = "Construct a `Couchbase Vector Search` vector store from raw documents."
    documentation = "https://python.langchain.com/docs/integrations/vectorstores/couchbase"
    icon = "Couchbase"
    field_order = [
        "couchbase_connection_string",
        "couchbase_username",
        "couchbase_password",
        "bucket_name",
        "scope_name",
        "collection_name",
        "index_name",
    ]

    def build_config(self):
        return {
            "inputs": {"display_name": "Input", "input_types": ["Document", "Record"]},
            "embedding": {"display_name": "Embedding"},
            "couchbase_connection_string": {"display_name": "Couchbase Cluster connection string", "required": True},
            "couchbase_username": {"display_name": "Couchbase username", "required": True},
            "couchbase_password": {"display_name": "Couchbase password", "password": True, "required": True},
            "bucket_name": {"display_name": "Bucket Name", "required": True},
            "scope_name": {"display_name": "Scope Name", "required": True},
            "collection_name": {"display_name": "Collection Name", "required": True},
            "index_name": {"display_name": "Index Name", "required": True},
        }

    def build(
        self,
        embedding: Embeddings,
        inputs: Optional[List[Record]] = None,
        bucket_name: str = "",
        scope_name: str = "",
        collection_name: str = "",
        index_name: str = "",
        couchbase_connection_string: str = "",
        couchbase_username: str = "",
        couchbase_password: str = "",
    ) -> Union[VectorStore, BaseRetriever]:
        try:
            from couchbase.auth import PasswordAuthenticator  # type: ignore
            from couchbase.cluster import Cluster  # type: ignore
            from couchbase.options import ClusterOptions  # type: ignore
            from langchain_community.vectorstores import CouchbaseVectorStore
        except ImportError as e:
            raise ImportError(
                "Failed to import Couchbase dependencies. Install it using `pip install langflow[couchbase] --pre`"
            ) from e

        try:
            auth = PasswordAuthenticator(couchbase_username, couchbase_password)
            options = ClusterOptions(auth)
            cluster = Cluster(couchbase_connection_string, options)

            cluster.wait_until_ready(timedelta(seconds=5))
        except Exception as e:
            raise ValueError(f"Failed to connect to Couchbase: {e}")
        documents = []
        for _input in inputs or []:
            if isinstance(_input, Record):
                documents.append(_input.to_lc_document())
            else:
                documents.append(_input)
        if documents:
            vector_store = CouchbaseVectorStore.from_documents(
                documents=documents,
                cluster=cluster,
                bucket_name=bucket_name,
                scope_name=scope_name,
                collection_name=collection_name,
                embedding=embedding,
                index_name=index_name,
            )
        else:
            vector_store = CouchbaseVectorStore(
                cluster=cluster,
                bucket_name=bucket_name,
                scope_name=scope_name,
                collection_name=collection_name,
                embedding=embedding,
                index_name=index_name,
            )
        return vector_store

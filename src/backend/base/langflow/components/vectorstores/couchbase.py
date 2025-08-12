from datetime import timedelta

from langflow.inputs.inputs import NestedDictInput, BoolInput
from langchain_couchbase.vectorstores import CouchbaseSearchVectorStore

from langflow.base.vectorstores.model import LCVectorStoreComponent, check_cached_vector_store
from langflow.helpers.data import docs_to_data
from langflow.io import HandleInput, IntInput, SecretStrInput, StrInput
from langflow.schema.data import Data


class CouchbaseSearchVectorStoreComponent(LCVectorStoreComponent):
    display_name = "Couchbase"
    description = "Couchbase Search Vector Store with search capabilities"
    name = "Couchbase"
    icon = "Couchbase"

    inputs = [
        SecretStrInput(
            name="couchbase_connection_string", display_name="Couchbase Cluster connection string", required=True
        ),
        StrInput(name="couchbase_username", display_name="Couchbase username", required=True),
        SecretStrInput(name="couchbase_password", display_name="Couchbase password", required=True),
        StrInput(name="bucket_name", display_name="Bucket Name", required=True),
        StrInput(name="scope_name", display_name="Scope Name", required=True),
        StrInput(name="collection_name", display_name="Collection Name", required=True),
        StrInput(name="index_name", display_name="Index Name", required=True),
        *LCVectorStoreComponent.inputs,
        BoolInput(
            name="enable_hybrid_search",
            display_name="Enable Hybrid Search",
            info="Flag to enable hybrid search with custom search options.",
            value=False,
            advanced=True,
        ),
        NestedDictInput(
            name="search_options",
            display_name="Hybrid Search Filter",
            info="Optional dictionary of filters to apply to the search query. Make sure to enable Hybrid search flag",
            advanced=True,
        ),
        HandleInput(name="embedding", display_name="Embedding", input_types=["Embeddings"]),
        IntInput(
            name="number_of_results",
            display_name="Number of Results",
            info="Number of results to return.",
            value=4,
            advanced=True,
        ),
    ]

    @check_cached_vector_store
    def build_vector_store(self) -> CouchbaseSearchVectorStore:
        try:
            from couchbase.auth import PasswordAuthenticator
            from couchbase.cluster import Cluster
            from couchbase.options import ClusterOptions
        except ImportError as e:
            msg = "Failed to import Couchbase dependencies. Install it using `uv pip install langflow[couchbase] --pre`"
            raise ImportError(msg) from e

        try:
            auth = PasswordAuthenticator(self.couchbase_username, self.couchbase_password)
            options = ClusterOptions(auth)
            cluster = Cluster(self.couchbase_connection_string, options)

            cluster.wait_until_ready(timedelta(seconds=5))
        except Exception as e:
            msg = f"Failed to connect to Couchbase: {e}"
            raise ValueError(msg) from e

        self.ingest_data = self._prepare_ingest_data()

        documents = []
        for _input in self.ingest_data or []:
            if isinstance(_input, Data):
                documents.append(_input.to_lc_document())
            else:
                documents.append(_input)

        if documents:
            couchbase_vs = CouchbaseSearchVectorStore.from_documents(
                documents=documents,
                cluster=cluster,
                bucket_name=self.bucket_name,
                scope_name=self.scope_name,
                collection_name=self.collection_name,
                embedding=self.embedding,
                index_name=self.index_name,
            )

        else:
            couchbase_vs = CouchbaseSearchVectorStore(
                cluster=cluster,
                bucket_name=self.bucket_name,
                scope_name=self.scope_name,
                collection_name=self.collection_name,
                embedding=self.embedding,
                index_name=self.index_name,
            )

        return couchbase_vs

    def search_documents(self) -> list[Data]:
        vector_store = self.build_vector_store()

        if self.search_query and isinstance(self.search_query, str) and self.search_query.strip():
            if self.enable_hybrid_search and self.search_options:
                docs = vector_store.similarity_search(
                    query=self.search_query,
                    search_options = self.search_options,
                    k=self.number_of_results,
                )
            else:
                docs = vector_store.similarity_search(
                    query=self.search_query,
                    k=self.number_of_results,
                )
            data = docs_to_data(docs)
            self.status = data
            return data
        return []

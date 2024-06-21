from datetime import timedelta
from typing import List

from langchain_community.vectorstores import CouchbaseVectorStore
from langchain_core.retrievers import BaseRetriever

from langflow.custom import Component
from langflow.helpers.data import docs_to_data
from langflow.io import BoolInput, HandleInput, IntInput, Output, SecretStrInput, StrInput
from langflow.schema import Data


class CouchbaseVectorStoreComponent(Component):
    display_name = "Couchbase"
    description = "Couchbase Vector Store with search capabilities"
    documentation = "https://python.langchain.com/docs/modules/data_connection/vectorstores/integrations/couchbase"
    icon = "Couchbase"

    inputs = [
        StrInput(name="couchbase_connection_string", display_name="Couchbase Cluster connection string", required=True),
        StrInput(name="couchbase_username", display_name="Couchbase username", required=True),
        SecretStrInput(name="couchbase_password", display_name="Couchbase password", required=True),
        StrInput(name="bucket_name", display_name="Bucket Name", required=True),
        StrInput(name="scope_name", display_name="Scope Name", required=True),
        StrInput(name="collection_name", display_name="Collection Name", required=True),
        StrInput(name="index_name", display_name="Index Name", required=True),
        HandleInput(name="embedding", display_name="Embedding", input_types=["Embeddings"]),
        HandleInput(
            name="vector_store_inputs",
            display_name="Vector Store Inputs",
            input_types=["Document", "Data"],
            is_list=True,
        ),
        BoolInput(
            name="add_to_vector_store",
            display_name="Add to Vector Store",
            info="If true, the Vector Store Inputs will be added to the Vector Store.",
        ),
        StrInput(name="search_input", display_name="Search Input"),
        IntInput(
            name="number_of_results",
            display_name="Number of Results",
            info="Number of results to return.",
            value=4,
            advanced=True,
        ),
    ]

    outputs = [
        Output(
            display_name="Vector Store",
            name="vector_store",
            method="build_vector_store",
            output_type=CouchbaseVectorStore,
        ),
        Output(
            display_name="Base Retriever",
            name="base_retriever",
            method="build_base_retriever",
            output_type=BaseRetriever,
        ),
        Output(display_name="Search Results", name="search_results", method="search_documents"),
    ]

    def build_vector_store(self) -> CouchbaseVectorStore:
        return self._build_couchbase()

    def _build_couchbase(self) -> CouchbaseVectorStore:
        try:
            from couchbase.auth import PasswordAuthenticator  # type: ignore
            from couchbase.cluster import Cluster  # type: ignore
            from couchbase.options import ClusterOptions  # type: ignore
        except ImportError as e:
            raise ImportError(
                "Failed to import Couchbase dependencies. Install it using `pip install langflow[couchbase] --pre`"
            ) from e

        try:
            auth = PasswordAuthenticator(self.couchbase_username, self.couchbase_password)
            options = ClusterOptions(auth)
            cluster = Cluster(self.couchbase_connection_string, options)

            cluster.wait_until_ready(timedelta(seconds=5))
        except Exception as e:
            raise ValueError(f"Failed to connect to Couchbase: {e}")

        if self.add_to_vector_store:
            documents = []
            for _input in self.vector_store_inputs or []:
                if isinstance(_input, Data):
                    documents.append(_input.to_lc_document())
                else:
                    documents.append(_input)

            if documents:
                couchbase_vs = CouchbaseVectorStore.from_documents(
                    documents=documents,
                    cluster=cluster,
                    bucket_name=self.bucket_name,
                    scope_name=self.scope_name,
                    collection_name=self.collection_name,
                    embedding=self.embedding,
                    index_name=self.index_name,
                )
            else:
                couchbase_vs = CouchbaseVectorStore(
                    cluster=cluster,
                    bucket_name=self.bucket_name,
                    scope_name=self.scope_name,
                    collection_name=self.collection_name,
                    embedding=self.embedding,
                    index_name=self.index_name,
                )
        else:
            couchbase_vs = CouchbaseVectorStore(
                cluster=cluster,
                bucket_name=self.bucket_name,
                scope_name=self.scope_name,
                collection_name=self.collection_name,
                embedding=self.embedding,
                index_name=self.index_name,
            )

        return couchbase_vs

    def search_documents(self) -> List[Data]:
        vector_store = self._build_couchbase()

        if self.search_input and isinstance(self.search_input, str) and self.search_input.strip():
            docs = vector_store.similarity_search(
                query=self.search_input,
                k=self.number_of_results,
            )

            data = docs_to_data(docs)
            self.status = data
            return data
        else:
            return []

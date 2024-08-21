from typing import List

from langchain_community.vectorstores import SupabaseVectorStore
from supabase.client import Client, create_client

from langflow.base.vectorstores.model import LCVectorStoreComponent, check_cached_vector_store
from langflow.helpers.data import docs_to_data
from langflow.io import HandleInput, IntInput, StrInput, SecretStrInput, DataInput, MultilineInput
from langflow.schema import Data


class SupabaseVectorStoreComponent(LCVectorStoreComponent):
    display_name = "Supabase"
    description = "Supabase Vector Store with search capabilities"
    documentation = "https://python.langchain.com/v0.2/docs/integrations/vectorstores/supabase/"
    name = "SupabaseVectorStore"
    icon = "Supabase"

    inputs = [
        StrInput(name="supabase_url", display_name="Supabase URL", required=True),
        SecretStrInput(name="supabase_service_key", display_name="Supabase Service Key", required=True),
        StrInput(name="table_name", display_name="Table Name", advanced=True),
        StrInput(name="query_name", display_name="Query Name"),
        MultilineInput(name="search_query", display_name="Search Query"),
        DataInput(
            name="ingest_data",
            display_name="Ingest Data",
            is_list=True,
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
    def build_vector_store(self) -> SupabaseVectorStore:
        supabase: Client = create_client(self.supabase_url, supabase_key=self.supabase_service_key)

        documents = []
        for _input in self.ingest_data or []:
            if isinstance(_input, Data):
                documents.append(_input.to_lc_document())
            else:
                documents.append(_input)

        if documents:
            supabase_vs = SupabaseVectorStore.from_documents(
                documents=documents,
                embedding=self.embedding,
                query_name=self.query_name,
                client=supabase,
                table_name=self.table_name,
            )
        else:
            supabase_vs = SupabaseVectorStore(
                client=supabase,
                embedding=self.embedding,
                table_name=self.table_name,
                query_name=self.query_name,
            )

        return supabase_vs

    def search_documents(self) -> List[Data]:
        vector_store = self.build_vector_store()

        if self.search_query and isinstance(self.search_query, str) and self.search_query.strip():
            docs = vector_store.similarity_search(
                query=self.search_query,
                k=self.number_of_results,
            )

            data = docs_to_data(docs)
            self.status = data
            return data
        else:
            return []

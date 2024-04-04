from typing import List

from langchain_community.vectorstores.supabase import SupabaseVectorStore
from supabase.client import Client, create_client

from langflow.components.vectorstores.base.model import LCVectorStoreComponent
from langflow.field_typing import Embeddings, Text
from langflow.schema import Record


class SupabaseSearchComponent(LCVectorStoreComponent):
    display_name = "Supabase Search"
    description = "Search a Supabase Vector Store for similar documents."
    icon = "Supabase"

    def build_config(self):
        return {
            "search_type": {
                "display_name": "Search Type",
                "options": ["Similarity", "MMR"],
            },
            "input_value": {"display_name": "Input"},
            "embedding": {"display_name": "Embedding"},
            "query_name": {"display_name": "Query Name"},
            "search_kwargs": {"display_name": "Search Kwargs", "advanced": True},
            "supabase_service_key": {"display_name": "Supabase Service Key"},
            "supabase_url": {"display_name": "Supabase URL"},
            "table_name": {"display_name": "Table Name", "advanced": True},
            "number_of_results": {
                "display_name": "Number of Results",
                "info": "Number of results to return.",
                "advanced": True,
            },
        }

    def build(
        self,
        input_value: Text,
        search_type: str,
        embedding: Embeddings,
        number_of_results: int = 4,
        query_name: str = "",
        supabase_service_key: str = "",
        supabase_url: str = "",
        table_name: str = "",
    ) -> List[Record]:
        supabase: Client = create_client(supabase_url, supabase_key=supabase_service_key)
        vector_store = SupabaseVectorStore(
            client=supabase,
            embedding=embedding,
            table_name=table_name,
            query_name=query_name,
        )
        return self.search_with_vector_store(input_value, search_type, vector_store, k=number_of_results)

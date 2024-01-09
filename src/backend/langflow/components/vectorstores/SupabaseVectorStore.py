
from langflow import CustomComponent
from typing import Optional, List
from langchain.vectorstores import SupabaseVectorStore
from langchain.field_typing import (
    Document,
    Embeddings,
    NestedDict,
)

class SupabaseComponent(CustomComponent):
    display_name = "Supabase"
    description = "Return VectorStore initialized from texts and embeddings."

    def build_config(self):
        return {
            "documents": {"display_name": "Documents"},
            "embedding": {"display_name": "Embedding"},
            "query_name": {"display_name": "Query Name"},
            "search_kwargs": {"display_name": "Search Kwargs"},
            "supabase_service_key": {"display_name": "Supabase Service Key"},
            "supabase_url": {"display_name": "Supabase URL"},
            "table_name": {"display_name": "Table Name"},
        }

    def build(
        self,
        embedding: Embeddings,
        documents: Optional[List[Document]] = None,
        query_name: str = '',
        search_kwargs: NestedDict = {},
        supabase_service_key: str = '',
        supabase_url: str = '',
        table_name: str = '',
    ) -> SupabaseVectorStore:
        return SupabaseVectorStore(
            documents=documents,
            embedding=embedding,
            query_name=query_name,
            search_kwargs=search_kwargs,
            supabase_service_key=supabase_service_key,
            supabase_url=supabase_url,
            table_name=table_name,
        )

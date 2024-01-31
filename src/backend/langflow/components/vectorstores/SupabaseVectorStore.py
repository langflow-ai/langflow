from typing import List, Union

from langchain.schema import BaseRetriever
from langchain_community.vectorstores import VectorStore
from langchain_community.vectorstores.supabase import SupabaseVectorStore
from langflow import CustomComponent
from langflow.field_typing import Document, Embeddings, NestedDict
from supabase.client import Client, create_client


class SupabaseComponent(CustomComponent):
    display_name = "Supabase"
    description = "Return VectorStore initialized from texts and embeddings."

    def build_config(self):
        return {
            "documents": {"display_name": "Documents"},
            "embedding": {"display_name": "Embedding"},
            "query_name": {"display_name": "Query Name"},
            "search_kwargs": {"display_name": "Search Kwargs", "advanced": True},
            "supabase_service_key": {"display_name": "Supabase Service Key"},
            "supabase_url": {"display_name": "Supabase URL"},
            "table_name": {"display_name": "Table Name", "advanced": True},
        }

    def build(
        self,
        embedding: Embeddings,
        documents: List[Document],
        query_name: str = "",
        search_kwargs: NestedDict = {},
        supabase_service_key: str = "",
        supabase_url: str = "",
        table_name: str = "",
    ) -> Union[VectorStore, SupabaseVectorStore, BaseRetriever]:
        supabase: Client = create_client(supabase_url, supabase_key=supabase_service_key)
        return SupabaseVectorStore.from_documents(
            documents=documents,
            embedding=embedding,
            query_name=query_name,
            search_kwargs=search_kwargs,
            client=supabase,
            table_name=table_name,
        )

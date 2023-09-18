from typing import List, Optional, Union
from langflow import CustomComponent

from langchain.vectorstores import SupabaseVectorStore
from langchain.vectorstores.base import VectorStore
from langchain.schema import BaseRetriever
from langchain.schema import Document
from langchain.embeddings.base import Embeddings
from supabase.client import Client, create_client


class SupabaseComponent(CustomComponent):
    """
    A custom component for implementing a Vector Store using Supabase.
    """

    display_name: str = "Supabase (Custom Component)"
    description: str = "Implementation of Vector Store using Supabase"
    documentation = (
        "https://python.langchain.com/docs/integrations/vectorstores/supabase"
    )
    beta = True

    def build_config(self):
        return {
            "query_name": {"display_name": "Query Name"},
            "api_key": {"display_name": "Service Key", "password": True},
            "url": {"display_name": "Server URL"},
            "table_name": {"display_name": "Table Name"},
            "code": {"display_name": "Code", "show": False},
            "documents": {"display_name": "Documents", "is_list": True},
            "embedding": {"display_name": "Embedding"},
        }

    def build(
        self,
        api_key: str,
        url: str,
        table_name: str,
        embeddings: Embeddings,
        query_name: Optional[str] = None,
        documents: Optional[List[Document]] = None,
    ) -> Union[VectorStore, BaseRetriever]:
        supabase: Client = create_client(supabase_key=api_key, supabase_url=url)

        if documents:
            return SupabaseVectorStore.from_documents(
                client=supabase,
                query_name=query_name,
                table_name=table_name,
                documents=documents,
                embedding=embeddings,
            )

        return SupabaseVectorStore(
            client=supabase,
            query_name=query_name,
            table_name=table_name,
            embedding=embeddings,
        )

from typing import List, Optional, Union

from langchain.schema import BaseRetriever
from langchain_community.vectorstores import VectorStore
from langchain_community.vectorstores.supabase import SupabaseVectorStore
from supabase.client import Client, create_client

from langflow.field_typing import Embeddings
from langflow.interface.custom.custom_component import CustomComponent
from langflow.schema.schema import Record


class SupabaseComponent(CustomComponent):
    display_name = "Supabase"
    description = "Return VectorStore initialized from texts and embeddings."

    def build_config(self):
        return {
            "inputs": {"display_name": "Input", "input_types": ["Document", "Record"]},
            "embedding": {"display_name": "Embedding"},
            "query_name": {"display_name": "Query Name"},
            "supabase_service_key": {"display_name": "Supabase Service Key"},
            "supabase_url": {"display_name": "Supabase URL"},
            "table_name": {"display_name": "Table Name", "advanced": True},
        }

    def build(
        self,
        embedding: Embeddings,
        inputs: Optional[List[Record]] = None,
        query_name: str = "",
        supabase_service_key: str = "",
        supabase_url: str = "",
        table_name: str = "",
    ) -> Union[VectorStore, SupabaseVectorStore, BaseRetriever]:
        supabase: Client = create_client(supabase_url, supabase_key=supabase_service_key)
        documents = []
        for _input in inputs or []:
            if isinstance(_input, Record):
                documents.append(_input.to_lc_document())
            else:
                documents.append(_input)
        return SupabaseVectorStore.from_documents(
            documents=documents,
            embedding=embedding,
            query_name=query_name,
            client=supabase,
            table_name=table_name,
        )

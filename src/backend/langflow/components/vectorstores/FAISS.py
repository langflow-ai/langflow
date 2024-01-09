
from langflow import CustomComponent
from langchain.vectorstores import FAISS
from typing import Optional, List
from langflow.field_typing import (
    Document,
    Embeddings,
    NestedDict,
)

class FAISSComponent(CustomComponent):
    display_name = "FAISS"
    description = "Construct FAISS wrapper from raw documents."
    documentation = "https://python.langchain.com/docs/modules/data_connection/vectorstores/integrations/faiss"

    def build_config(self):
        return {
            "documents": {"display_name": "Documents"},
            "embedding": {"display_name": "Embedding"},
            "folder_path": {"display_name": "Local Path"},
            "index_name": {"display_name": "Index Name"},
            "search_kwargs": {"display_name": "Search Kwargs", "advanced": True},
        }

    def build(
        self,
        embedding: Embeddings,
        documents: Optional[List[Document]] = None,
        folder_path: str = "",
        index_name: str = "",
        search_kwargs: Optional[NestedDict] = None,
    ) -> FAISS:
        return FAISS(
            embedding=embedding,
            documents=documents,
            folder_path=folder_path,
            index_name=index_name,
            search_kwargs=search_kwargs or {},
        )

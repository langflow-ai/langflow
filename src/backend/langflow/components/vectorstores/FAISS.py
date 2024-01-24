from langflow import CustomComponent
from langchain_community.vectorstores.faiss import FAISS
from typing import Optional, List, Union
from langchain.schema import BaseRetriever
from langchain.vectorstores.base import VectorStore
from langflow.field_typing import (
    Document,
    Embeddings,
)


class FAISSComponent(CustomComponent):
    display_name = "FAISS"
    description = "Construct FAISS wrapper from raw documents."
    documentation = "https://python.langchain.com/docs/modules/data_connection/vectorstores/integrations/faiss"

    def build_config(self):
        return {
            "documents": {"display_name": "Documents"},
            "embedding": {"display_name": "Embedding"},
        }

    def build(
        self,
        embedding: Embeddings,
        documents: Optional[List[Document]] = None,
    ) -> Union[VectorStore, FAISS, BaseRetriever]:
        return FAISS.from_documents(documents=documents, embedding=embedding)

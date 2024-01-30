from typing import List, Union

from langchain.schema import BaseRetriever
from langchain_community.vectorstores import VectorStore
from langchain_community.vectorstores.faiss import FAISS
from langflow import CustomComponent
from langflow.field_typing import Document, Embeddings


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
        documents: List[Document],
    ) -> Union[VectorStore, FAISS, BaseRetriever]:
        return FAISS.from_documents(documents=documents, embedding=embedding)

from typing import List, Union

from langchain.schema import BaseRetriever
from langchain_community.vectorstores import VectorStore
from langchain_community.vectorstores.faiss import FAISS

from langflow import CustomComponent
from langflow.field_typing import Document, Embeddings


class FAISSComponent(CustomComponent):
    display_name = "FAISS"
    description = "Ingest documents into FAISS Vector Store."
    documentation = "https://python.langchain.com/docs/modules/data_connection/vectorstores/integrations/faiss"

    def build_config(self):
        return {
            "documents": {"display_name": "Documents"},
            "embedding": {"display_name": "Embedding"},
            "folder_path": {
                "display_name": "Folder Path",
                "info": "Path to save the FAISS index. It will be relative to where Langflow is running.",
            },
        }

    def build(
        self,
        embedding: Embeddings,
        documents: List[Document],
        folder_path: str,
        index_name: str = "langflow_index",
    ) -> Union[VectorStore, FAISS, BaseRetriever]:
        vector_store = FAISS.from_documents(documents=documents, embedding=embedding)
        if not folder_path:
            raise ValueError("Folder path is required to save the FAISS index.")
        path = self.resolve_path(folder_path)
        vector_store.save_local(str(path), index_name)

from typing import List

from langchain.text_splitter import CharacterTextSplitter
from langchain_core.documents.base import Document
from langflow import CustomComponent


class CharacterTextSplitterComponent(CustomComponent):
    display_name = "CharacterTextSplitter"
    description = "Splitting text that looks at characters."

    def build_config(self):
        return {
            "documents": {"display_name": "Documents"},
            "chunk_overlap": {"display_name": "Chunk Overlap", "default": 200},
            "chunk_size": {"display_name": "Chunk Size", "default": 1000},
            "separator": {"display_name": "Separator", "default": "\n"},
        }

    def build(
        self,
        documents: List[Document],
        chunk_overlap: int = 200,
        chunk_size: int = 1000,
        separator: str = "\n",
    ) -> List[Document]:
        docs = CharacterTextSplitter(
            chunk_overlap=chunk_overlap,
            chunk_size=chunk_size,
            separator=separator,
        ).split_documents(documents)
        self.status = docs
        return docs

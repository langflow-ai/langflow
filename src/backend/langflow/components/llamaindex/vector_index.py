"""Vector Index."""

from typing import Optional, List
from langflow import CustomComponent
from langflow.utils.util import build_loader_repr_from_documents
from llama_index.schema import Document, TextNode
from llama_index.node_parser import SentenceSplitter
from llama_index import VectorStoreIndex
from langflow.field_typing import Object


class VectorIndexComponent(CustomComponent):
    display_name: str = "Vector Index"
    description: str = "Indexes text into a vector store"
    
    def build_config(self):
        return {
            "documents": {
                "display_name": "Documents",
                "info": "The documents to ingest",
            }
        }
    
    def build(
        self,
        documents: List[TextNode],
    ) -> Object:
        """Build."""
        return VectorStoreIndex(documents=documents)

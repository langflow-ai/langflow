"""Vector Index Retriever."""

from typing import Optional, List, cast
from langflow import CustomComponent
from langflow.utils.util import build_loader_repr_from_documents
from llama_index.schema import Document, TextNode
from llama_index.node_parser import SentenceSplitter
from llama_index import VectorStoreIndex
from langflow.field_typing import Object
from llama_index.retrievers import VectorIndexRetriever


class VectorIndexRetrieverComponent(CustomComponent):
    display_name: str = "Vector Index Retriever" 
    description: str = "Retrieves nodes from a vector index"
    
    def build_config(self):
        return {
            "vector_index": {
                "display_name": "Vector Index",
                "info": "The index that you'll be loading from",
            },
            "similarity_top_k": {
                "display_name": "Similarity Top K",
                "info": "The number of results to return",
            }
        }
    
    def build(
        self,
        vector_index: Object,
        similarity_top_k: int = 10,
    ) -> Object:
        """Build."""
        
        vector_index = cast(VectorStoreIndex, vector_index)
        return VectorIndexRetriever(
            vector_index, similarity_top_k=similarity_top_k
        )

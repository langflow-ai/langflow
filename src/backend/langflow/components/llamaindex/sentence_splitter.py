"""Sentence splitter."""

from typing import Optional, List, cast
from langflow import CustomComponent
from langflow.utils.util import build_loader_repr_from_documents
from langflow.field_typing import Object
from llama_index.schema import Document, TextNode
from llama_index.node_parser import SentenceSplitter

class SentenceSplitterComponent(CustomComponent):
    display_name: str = "Sentence Splitter"
    description: str = "Splits text into paragraphs, and then sentences"

    def build_config(self):
        return {
            "documents": {
                "display_name": "Documents",
                "info": "The documents to split.",
            },
            "chunk_size": {
                "display_name": "Chunk Size",
                "info": "The maximum length of each chunk.",
                "field_type": "int",
                "value": 1024,
            },
            "chunk_overlap": {
                "display_name": "Chunk Overlap",
                "info": "The amount of overlap between chunks.",
                "field_type": "int",
                "value": 200,
            },
            "separator": {
                "display_name": "Separator",
                "info": 'Default separator for splitting into words',
                "value": " ",
            },
            "paragraph_separator": {
                "display_name": "Paragraph Separator",
                "info": 'Default separator for splitting into paragraphs',
                "value": "\n\n\n",
            },
            "secondary_chunking_regex": {
                "display_name": "Secondary Chunking Regex",
                "info": 'Backup regex for splitting into sentences',
                "value": "[^,.;。？！]+[,.;。？！]?"
            },
        }

    def build(
        self,
        documents: Object,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        separator: str = " ",
        paragraph_separator: str = "\n\n\n",
        secondary_chunking_regex: str = "[^,.;。？！]+[,.;。？！]?",
    ) -> Object:
        """
        Split text into sentence-based chunks of a specified length.

        Args:
            documents (list[TextNode]): The documents to split.
            chunk_size (int): The maximum length of each chunk.
            chunk_overlap (int): The amount of overlap between chunks.
            separator (str): The separator for splitting into words.
            paragraph_separator (str): The separator for splitting into paragraphs.
            secondary_chunking_regex (str): The regex for splitting into sentences.

        Returns:
            List[TextNode]: The chunks of text.
        """

        documents = cast(List[TextNode], documents)

        node_parser = SentenceSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separator=separator,
            paragraph_separator=paragraph_separator,
            secondary_chunking_regex=secondary_chunking_regex,
        )
        
        nodes = node_parser.get_nodes_from_documents(documents)
        return nodes

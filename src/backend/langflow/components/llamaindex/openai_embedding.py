"""OpenAI Embedding."""

from typing import Optional, List, cast
from langflow import CustomComponent
from langflow.utils.util import build_loader_repr_from_documents
from langflow.field_typing import Object
from llama_index.schema import Document, TextNode, MetadataMode
from llama_index.node_parser import SentenceSplitter
from llama_index.embeddings import OpenAIEmbedding

class OpenAIEmbeddingComponent(CustomComponent):
    display_name: str = "OpenAI Embeddings"
    description: str = "Embed text using OpenAI embedding models."

    def build_config(self):
        return {
            "model": {
                "display_name": "Model",
                "info": "The model to use.",
                "value": "text-embedding-ada-002",
            },
            "documents": {
                "display_name": "Documents",
                "info": "The documents to embed.",
            }
        }

    def build(
        self,
        documents: Object,
        model: str = "text-embedding-ada-002",
    ) -> Object:
        """
        Embed text using OpenAI embedding models.

        Args:
            documents (list[TextNode]): The documents to split.
            model (str, optional): The model to use. Defaults to "text-embedding-ada-002".

        Returns:
            list[str]: The chunks of text.
        """

        documents = cast(List[TextNode], documents)

        embed_model = OpenAIEmbedding(model=model)
        embeddings = embed_model.get_text_embedding_batch(
            [doc.get_content(metadata_mode=MetadataMode.EMBED) for doc in documents],
        )
        for doc, embedding in zip(documents, embeddings):
            doc.embedding = embedding

        return documents

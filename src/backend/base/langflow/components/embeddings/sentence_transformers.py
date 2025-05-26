from typing import Any, List

from langflow.base.embeddings.model import LCEmbeddingsModel
from langflow.field_typing import Embeddings
from langflow.inputs.inputs import DropdownInput, SecretStrInput
from langflow.io import FloatInput, MessageTextInput
from langflow.schema.dotdict import dotdict
from sentence_transformers import SentenceTransformer


class SentenceTransformerEmbeddings(LCEmbeddingsModel):
    display_name: str = "SentenceTransformer Embeddings"
    description: str = "Generate embeddings locally using SentenceTransformer."
    documentation: str = "https://www.sbert.net/"
    icon = "SentenceTransformers"

    inputs = [
        MessageTextInput(
            name="model_name",
            display_name="Model Name",
            value="all-MiniLM-L6-v2",
            required=True,
        ),
    ]

    def build_embeddings(self) -> Embeddings:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            raise ImportError("Please install sentence-transformers to use this component.") from e

        try:
            model = SentenceTransformer(self.model_name)
        except Exception as e:
            raise ValueError(f"Failed to load SentenceTransformer model: {e}") from e

        class LangflowEmbeddingWrapper:
            def embed_documents(self, texts: List[str]) -> List[List[float]]:
                return model.encode(texts, convert_to_numpy=True).tolist()

            def embed_query(self, text: str) -> List[float]:
                return model.encode(text, convert_to_numpy=True).tolist()

        return LangflowEmbeddingWrapper()
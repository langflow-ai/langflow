from langflow.base.embeddings.model import LCEmbeddingsModel
from langflow.field_typing import Embeddings
from langflow.io import MessageTextInput


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
            msg = "Please install sentence-transformers to use this component."
            raise ImportError(msg) from e

        try:
            model = SentenceTransformer(self.model_name)
        except Exception as e:
            msg = f"Failed to load SentenceTransformer model: {e}"
            raise ValueError(msg) from e

        class LangflowEmbeddingWrapper:
            def embed_documents(self, texts: list[str]) -> list[list[float]]:
                return model.encode(texts, convert_to_numpy=True).tolist()

            def embed_query(self, text: str) -> list[float]:
                return model.encode(text, convert_to_numpy=True).tolist()

        return LangflowEmbeddingWrapper()

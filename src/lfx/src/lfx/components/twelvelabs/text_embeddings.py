from twelvelabs import TwelveLabs

from lfx.base.embeddings.model import LCEmbeddingsModel
from lfx.field_typing import Embeddings
from lfx.io import DropdownInput, FloatInput, IntInput, SecretStrInput


class TwelveLabsTextEmbeddings(Embeddings):
    def __init__(self, api_key: str, model: str) -> None:
        self.client = TwelveLabs(api_key=api_key)
        self.model = model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        all_embeddings: list[list[float]] = []
        for text in texts:
            if not text:
                continue

            result = self.client.embed.create(model_name=self.model, text=text)

            if result.text_embedding and result.text_embedding.segments:
                for segment in result.text_embedding.segments:
                    all_embeddings.append([float(x) for x in segment.embeddings_float])
                    break  # Only take first segment for now

        return all_embeddings

    def embed_query(self, text: str) -> list[float]:
        result = self.client.embed.create(model_name=self.model, text=text)

        if result.text_embedding and result.text_embedding.segments:
            return [float(x) for x in result.text_embedding.segments[0].embeddings_float]
        return []


class TwelveLabsTextEmbeddingsComponent(LCEmbeddingsModel):
    display_name = "Twelve Labs Text Embeddings"
    description = "Generate embeddings using Twelve Labs text embedding models."
    icon = "TwelveLabs"
    name = "TwelveLabsTextEmbeddings"
    documentation = "https://github.com/twelvelabs-io/twelvelabs-developer-experience/blob/main/integrations/Langflow/TWELVE_LABS_COMPONENTS_README.md"

    inputs = [
        SecretStrInput(name="api_key", display_name="Twelve Labs API Key", value="TWELVELABS_API_KEY", required=True),
        DropdownInput(
            name="model",
            display_name="Model",
            advanced=False,
            options=["Marengo-retrieval-2.7"],
            value="Marengo-retrieval-2.7",
        ),
        IntInput(name="max_retries", display_name="Max Retries", value=3, advanced=True),
        FloatInput(name="request_timeout", display_name="Request Timeout", advanced=True),
    ]

    def build_embeddings(self) -> Embeddings:
        return TwelveLabsTextEmbeddings(api_key=self.api_key, model=self.model)

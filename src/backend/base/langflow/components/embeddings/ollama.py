from langchain_ollama import OllamaEmbeddings

from langflow.base.models.model import LCModelComponent
from langflow.field_typing import Embeddings
from langflow.io import MessageTextInput, Output


class OllamaEmbeddingsComponent(LCModelComponent):
    display_name: str = "Ollama Embeddings"
    description: str = "Generate embeddings using Ollama models."
    documentation = "https://python.langchain.com/docs/integrations/text_embedding/ollama"
    icon = "Ollama"
    name = "OllamaEmbeddings"

    inputs = [
        MessageTextInput(
            name="model",
            display_name="Ollama Model",
            value="nomic-embed-text",
        ),
        MessageTextInput(
            name="base_url",
            display_name="Ollama Base URL",
            value="http://localhost:11434",
        ),
    ]

    outputs = [
        Output(display_name="Embeddings", name="embeddings", method="build_embeddings"),
    ]

    def build_embeddings(self) -> Embeddings:
        try:
            output = OllamaEmbeddings(model=self.model, base_url=self.base_url)
        except Exception as e:
            msg = "Could not connect to Ollama API."
            raise ValueError(msg) from e
        return output

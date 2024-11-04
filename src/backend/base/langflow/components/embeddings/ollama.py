from langchain_ollama import OllamaEmbeddings

from langflow.base.models.model import LCModelComponent
from langflow.field_typing import Embeddings
from langflow.io import FloatInput, MessageTextInput, Output


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
            value="llama3.1",
        ),
        MessageTextInput(
            name="base_url",
            display_name="Ollama Base URL",
            value="http://localhost:11434",
        ),
        FloatInput(
            name="temperature",
            display_name="Model Temperature",
            value=0.1,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Embeddings", name="embeddings", method="build_embeddings"),
    ]

    def build_embeddings(self) -> Embeddings:
        try:
            output = OllamaEmbeddings(
                model=self.model,
                base_url=self.base_url,
                temperature=self.temperature,
            )
        except Exception as e:
            msg = "Could not connect to Ollama API."
            raise ValueError(msg) from e
        return output

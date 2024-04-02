from typing import Optional

from langchain.embeddings.base import Embeddings
from langchain_community.embeddings import OllamaEmbeddings

from langflow.interface.custom.custom_component import CustomComponent


class OllamaEmbeddingsComponent(CustomComponent):
    display_name: str = "Ollama Embeddings"
    description: str = "Generate embeddings using Ollama models."
    documentation = "https://python.langchain.com/docs/integrations/text_embedding/ollama"

    def build_config(self):
        return {
            "model": {
                "display_name": "Ollama Model",
            },
            "base_url": {"display_name": "Ollama Base URL"},
            "temperature": {"display_name": "Model Temperature"},
            "code": {"show": False},
        }

    def build(
        self,
        model: str = "llama2",
        base_url: str = "http://localhost:11434",
        temperature: Optional[float] = None,
    ) -> Embeddings:
        try:
            output = OllamaEmbeddings(model=model, base_url=base_url, temperature=temperature)  # type: ignore
        except Exception as e:
            raise ValueError("Could not connect to Ollama API.") from e
        return output

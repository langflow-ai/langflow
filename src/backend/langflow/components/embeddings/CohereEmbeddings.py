
from langflow import CustomComponent
from langchain.embeddings import CohereEmbeddings
from typing import Optional, Any


class CohereEmbeddingsComponent(CustomComponent):
    display_name = "CohereEmbeddings"
    description = "Cohere embedding models."

    def build_config(self):
        return {
            "async_client": {"display_name": "Async Client", "advanced": True},
            "client": {"display_name": "Client", "advanced": True},
            "cohere_api_key": {"display_name": "Cohere API Key"},
            "model": {"display_name": "Model", "default": "embed-english-v2.0", "advanced": True},
            "truncate": {"display_name": "Truncate", "advanced": True},
        }

    def build(
        self,
        async_client: Optional[Any] = None,
        client: Optional[Any] = None,
        cohere_api_key: Optional[str] = None,
        model: str = "embed-english-v2.0",
        truncate: Optional[str] = None,
    ) -> CohereEmbeddings:
        return CohereEmbeddings(
            async_client=async_client,
            client=client,
            cohere_api_key=cohere_api_key,
            model=model,
            truncate=truncate,
        )

from typing import Optional

from langchain_community.embeddings.cohere import CohereEmbeddings
from langflow import CustomComponent


class CohereEmbeddingsComponent(CustomComponent):
    display_name = "CohereEmbeddings"
    description = "Cohere embedding models."

    def build_config(self):
        return {
            "cohere_api_key": {"display_name": "Cohere API Key", "password": True},
            "model": {"display_name": "Model", "default": "embed-english-v2.0", "advanced": True},
            "truncate": {"display_name": "Truncate", "advanced": True},
            "max_retries": {"display_name": "Max Retries", "advanced": True},
            "user_agent": {"display_name": "User Agent", "advanced": True},
        }

    def build(
        self,
        request_timeout: Optional[float] = None,
        cohere_api_key: str = "",
        max_retries: Optional[int] = None,
        model: str = "embed-english-v2.0",
        truncate: Optional[str] = None,
        user_agent: str = "langchain",
    ) -> CohereEmbeddings:
        return CohereEmbeddings(  # type: ignore
            max_retries=max_retries,
            user_agent=user_agent,
            request_timeout=request_timeout,
            cohere_api_key=cohere_api_key,
            model=model,
            truncate=truncate,
        )

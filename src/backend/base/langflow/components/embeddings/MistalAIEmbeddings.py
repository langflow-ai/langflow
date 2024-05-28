from langchain_mistralai.embeddings import MistralAIEmbeddings
from pydantic.v1 import SecretStr

from langflow.custom import CustomComponent
from langflow.field_typing import Embeddings


class MistralAIEmbeddingsComponent(CustomComponent):
    display_name = "MistralAI Embeddings"
    description = "Generate embeddings using MistralAI models."

    def build_config(self):
        return {
            "model": {
                "display_name": "Model",
                "advanced": False,
                "options": ["mistral-embed"],
                "value": "mistral-embed",
            },
            "mistral_api_key": {
                "display_name": "Mistral API Key",
                "password": True,
                "advanced": False,
            },
            "max_concurrent_requests": {
                "display_name": "Max Concurrent Requests",
                "advanced": True,
                "value": 64,
            },
            "max_retries": {
                "display_name": "Max Retries",
                "advanced": True,
                "value": 5,
            },
            "timeout": {
                "display_name": "Request Timeout",
                "advanced": True,
                "value": 120,
            },
            "endpoint": {"display_name": "API Endpoint", "advanced": True, "value": "https://api.mistral.ai/v1/"},
        }

    def build(
        self,
        mistral_api_key: str,
        model: str = "mistral-embed",
        max_concurrent_requests: int = 64,
        max_retries: int = 5,
        timeout: int = 120,
        endpoint: str = "https://api.mistral.ai/v1/",
    ) -> Embeddings:
        if mistral_api_key:
            api_key = SecretStr(mistral_api_key)
        else:
            api_key = None

        return MistralAIEmbeddings(
            api_key=api_key,
            model=model,
            endpoint=endpoint,
            max_concurrent_requests=max_concurrent_requests,
            max_retries=max_retries,
            timeout=timeout,
        )

from langchain_community.embeddings.cohere import CohereEmbeddings

from langflow.base.models.model import LCModelComponent
from langflow.field_typing import Embeddings
from langflow.io import DropdownInput, FloatInput, IntInput, MessageTextInput, Output, SecretStrInput


class CohereEmbeddingsComponent(LCModelComponent):
    display_name = "Cohere Embeddings"
    description = "Generate embeddings using Cohere models."
    icon = "Cohere"
    name = "CohereEmbeddings"

    inputs = [
        SecretStrInput(name="cohere_api_key", display_name="Cohere API Key"),
        DropdownInput(
            name="model",
            display_name="Model",
            advanced=True,
            options=[
                "embed-english-v2.0",
                "embed-multilingual-v2.0",
                "embed-english-light-v2.0",
                "embed-multilingual-light-v2.0",
            ],
            value="embed-english-v2.0",
        ),
        MessageTextInput(name="truncate", display_name="Truncate", advanced=True),
        IntInput(name="max_retries", display_name="Max Retries", value=3, advanced=True),
        MessageTextInput(name="user_agent", display_name="User Agent", advanced=True, value="langchain"),
        FloatInput(name="request_timeout", display_name="Request Timeout", advanced=True),
    ]

    outputs = [
        Output(display_name="Embeddings", name="embeddings", method="build_embeddings"),
    ]

    def build_embeddings(self) -> Embeddings:
        return CohereEmbeddings(  # type: ignore
            cohere_api_key=self.cohere_api_key,
            model=self.model,
            truncate=self.truncate,
            max_retries=self.max_retries,
            user_agent=self.user_agent,
            request_timeout=self.request_timeout or None,
        )

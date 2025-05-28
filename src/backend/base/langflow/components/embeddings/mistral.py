from langchain_mistralai.embeddings import MistralAIEmbeddings
from pydantic.v1 import SecretStr

from langflow.base.models.model import LCModelComponent
from langflow.field_typing import Embeddings
from langflow.io import DropdownInput, IntInput, MessageTextInput, Output, SecretStrInput


class MistralAIEmbeddingsComponent(LCModelComponent):
    display_name = "MistralAI Embeddings"
    description = "Generate embeddings using MistralAI models."
    icon = "MistralAI"
    name = "MistalAIEmbeddings"

    inputs = [
        DropdownInput(
            name="model",
            display_name="Model",
            advanced=False,
            options=["mistral-embed"],
            value="mistral-embed",
        ),
        SecretStrInput(name="mistral_api_key", display_name="Mistral API Key", required=True),
        IntInput(
            name="max_concurrent_requests",
            display_name="Max Concurrent Requests",
            advanced=True,
            value=64,
        ),
        IntInput(name="max_retries", display_name="Max Retries", advanced=True, value=5),
        IntInput(name="timeout", display_name="Request Timeout", advanced=True, value=120),
        MessageTextInput(
            name="endpoint",
            display_name="API Endpoint",
            advanced=True,
            value="https://api.mistral.ai/v1/",
        ),
    ]

    outputs = [
        Output(display_name="Embeddings", name="embeddings", method="build_embeddings"),
    ]

    def build_embeddings(self) -> Embeddings:
        if not self.mistral_api_key:
            msg = "Mistral API Key is required"
            raise ValueError(msg)

        api_key = SecretStr(self.mistral_api_key).get_secret_value()

        return MistralAIEmbeddings(
            api_key=api_key,
            model=self.model,
            endpoint=self.endpoint,
            max_concurrent_requests=self.max_concurrent_requests,
            max_retries=self.max_retries,
            timeout=self.timeout,
        )

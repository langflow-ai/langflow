from urllib.parse import urlparse

import requests
from langchain_community.embeddings.huggingface import HuggingFaceInferenceAPIEmbeddings
from pydantic.v1.types import SecretStr

from langflow.base.embeddings.model import LCEmbeddingsModel
from langflow.field_typing import Embeddings
from langflow.io import MessageTextInput, Output, SecretStrInput


class HuggingFaceInferenceAPIEmbeddingsComponent(LCEmbeddingsModel):
    display_name = "HuggingFace Embeddings Inference"
    description = "Generate embeddings using HuggingFace Text Embeddings Inference (TEI)"
    documentation = "https://huggingface.co/docs/text-embeddings-inference/index"
    icon = "HuggingFace"
    name = "HuggingFaceInferenceAPIEmbeddings"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            advanced=True,
            info="Required for non-local inference endpoints. Local inference does not require an API Key.",
        ),
        MessageTextInput(
            name="inference_endpoint",
            display_name="Inference Endpoint",
            required=True,
            value="http://localhost:8080",
            info="Custom inference endpoint URL.",
        ),
        MessageTextInput(
            name="model_name",
            display_name="Model Name",
            value="BAAI/bge-large-en-v1.5",
            info="The name of the model to use for text embeddings.",
        ),
    ]

    outputs = [
        Output(display_name="Embeddings", name="embeddings", method="build_embeddings"),
    ]

    def validate_inference_endpoint(self, inference_endpoint: str) -> bool:
        parsed_url = urlparse(inference_endpoint)
        if not all([parsed_url.scheme, parsed_url.netloc]):
            raise ValueError(
                f"Invalid inference endpoint format: '{self.inference_endpoint}'. Please ensure the URL includes both a scheme (e.g., 'http://' or 'https://') and a domain name. Example: 'http://localhost:8080' or 'https://api.example.com'"
            )

        try:
            response = requests.get(f"{inference_endpoint}/health", timeout=5)
        except requests.RequestException:
            raise ValueError(
                f"Inference endpoint '{inference_endpoint}' is not responding. Please ensure the URL is correct and the service is running."
            )

        if response.status_code != 200:
            raise ValueError(f"HuggingFace health check failed: {response.status_code}")
        # returning True to solve linting error
        return True

    def build_embeddings(self) -> Embeddings:
        if not self.inference_endpoint:
            raise ValueError("Inference endpoint is required")

        self.validate_inference_endpoint(self.inference_endpoint)

        # Check if the inference endpoint is local
        is_local_url = self.inference_endpoint.startswith(("http://localhost", "http://127.0.0.1"))

        # Use a dummy key for local URLs if no key is provided.
        # Refer https://python.langchain.com/v0.2/api_reference/community/embeddings/langchain_community.embeddings.huggingface.HuggingFaceInferenceAPIEmbeddings.html
        if not self.api_key and is_local_url:
            api_key = SecretStr("DummyAPIKeyForLocalDeployment")
        elif not self.api_key:
            raise ValueError("API Key is required for non-local inference endpoints")
        else:
            api_key = SecretStr(self.api_key)

        return HuggingFaceInferenceAPIEmbeddings(
            api_key=api_key, api_url=self.inference_endpoint, model_name=self.model_name
        )

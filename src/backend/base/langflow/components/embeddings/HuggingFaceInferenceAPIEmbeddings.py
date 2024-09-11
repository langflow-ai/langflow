from langchain_community.embeddings.huggingface import HuggingFaceInferenceAPIEmbeddings
from pydantic.v1.types import SecretStr
import requests
from urllib.parse import urlparse

from langflow.base.models.model import LCModelComponent
from langflow.field_typing import Embeddings
from langflow.io import MessageTextInput, Output, SecretStrInput


class HuggingFaceInferenceAPIEmbeddingsComponent(LCModelComponent):
    display_name = "HuggingFace Embeddings Inference"
    description = "Generate embeddings using HuggingFace Text Embeddings Inference (TEI)"
    documentation = "https://huggingface.co/docs/text-embeddings-inference/en/index"
    icon = "HuggingFace"
    name = "HuggingFaceInferenceAPIEmbeddings"

    inputs = [
        SecretStrInput(
            name="api_key", display_name="API Key", advanced=True, info="The API key is required for non-local API URLs"
        ),
        MessageTextInput(name="api_url", display_name="API URL", required=True, value="http://localhost:8080"),
        MessageTextInput(name="model_name", display_name="Model Name", value="BAAI/bge-large-en-v1.5"),
    ]

    outputs = [
        Output(display_name="Embeddings", name="embeddings", method="build_embeddings"),
    ]

    def validate_api_url(self, api_url: str) -> bool:
        parsed_url = urlparse(api_url)
        if not all([parsed_url.scheme, parsed_url.netloc]):
            raise ValueError("Invalid API URL format")

        try:
            response = requests.get(f"{api_url}/health", timeout=5)
            return response.status_code == 200
        except requests.RequestException:
            return False

    def build_embeddings(self) -> Embeddings:
        if not self.api_url:
            raise ValueError("API URL is required")

        if not self.validate_api_url(self.api_url):
            raise ValueError("API URL is invalid or the service is not responding")

        # Check if the API URL is local
        is_local_url = self.api_url.startswith(("http://localhost", "http://127.0.0.1"))

        # Use a dummy key for local URLs if no key is provided
        if not self.api_key and is_local_url:
            api_key = SecretStr("DummyAPIKeyForLocalDeployment")
        elif not self.api_key:
            raise ValueError("API Key is required for non-local API URLs")
        else:
            api_key = SecretStr(self.api_key)

        return HuggingFaceInferenceAPIEmbeddings(api_key=api_key, api_url=self.api_url, model_name=self.model_name)

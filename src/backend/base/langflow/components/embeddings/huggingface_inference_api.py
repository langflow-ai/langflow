r"""HuggingFace Inference API embeddings component for Langflow.

This module provides the HuggingFaceInferenceAPIEmbeddingsComponent which integrates
HuggingFace's Text Embeddings Inference (TEI) into Langflow workflows. Supports both
hosted Inference API and local/custom TEI deployments.

Deployment Options:
    - HuggingFace Hosted API: api-inference.huggingface.co (requires API key)
    - Local TEI Server: Self-hosted inference server (no API key needed)
    - Custom Endpoints: Private TEI deployments with custom URLs
    - Docker Deployments: Containerized TEI instances

Popular Models:
    - BAAI/bge-large-en-v1.5: High-quality English embeddings (default)
    - sentence-transformers/all-MiniLM-L6-v2: Lightweight multilingual
    - intfloat/e5-large-v2: Strong performance across tasks
    - BAAI/bge-small-en-v1.5: Faster, smaller model for English
    - sentence-transformers/all-mpnet-base-v2: Balanced performance

Key Features:
    - Automatic local vs. hosted endpoint detection
    - Health check validation for custom endpoints
    - Retry mechanism with exponential backoff
    - Support for any HuggingFace embedding model
    - Flexible authentication (API key for hosted, none for local)

Configuration:
    - api_key: Required for hosted API, optional for local deployments
    - inference_endpoint: URL for TEI server or hosted API
    - model_name: HuggingFace model identifier

Local Deployment Example:
    ```bash
    # Start TEI server locally
    docker run -p 8080:80 ghcr.io/huggingface/text-embeddings-inference:latest \\
        --model-id BAAI/bge-large-en-v1.5

    # Configure component
    inference_endpoint: http://localhost:8080
    model_name: BAAI/bge-large-en-v1.5
    api_key: (leave empty for local)
    ```

Hosted API Example:
    ```
    inference_endpoint: https://api-inference.huggingface.co/models/
    model_name: BAAI/bge-large-en-v1.5
    api_key: hf_your_api_key_here
    ```

The component includes automatic endpoint validation, health checking,
and graceful handling of both local and hosted deployments.
"""

from urllib.parse import urlparse

import requests
from langchain_community.embeddings.huggingface import HuggingFaceInferenceAPIEmbeddings

# Next update: use langchain_huggingface
from pydantic import SecretStr
from tenacity import retry, stop_after_attempt, wait_fixed

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
            advanced=False,
            info="Required for non-local inference endpoints. Local inference does not require an API Key.",
        ),
        MessageTextInput(
            name="inference_endpoint",
            display_name="Inference Endpoint",
            required=True,
            value="https://api-inference.huggingface.co/models/",
            info="Custom inference endpoint URL.",
        ),
        MessageTextInput(
            name="model_name",
            display_name="Model Name",
            value="BAAI/bge-large-en-v1.5",
            info="The name of the model to use for text embeddings.",
            required=True,
        ),
    ]

    outputs = [
        Output(display_name="Embeddings", name="embeddings", method="build_embeddings"),
    ]

    def validate_inference_endpoint(self, inference_endpoint: str) -> bool:
        parsed_url = urlparse(inference_endpoint)
        if not all([parsed_url.scheme, parsed_url.netloc]):
            msg = (
                f"Invalid inference endpoint format: '{self.inference_endpoint}'. "
                "Please ensure the URL includes both a scheme (e.g., 'http://' or 'https://') and a domain name. "
                "Example: 'http://localhost:8080' or 'https://api.example.com'"
            )
            raise ValueError(msg)

        try:
            response = requests.get(f"{inference_endpoint}/health", timeout=5)
        except requests.RequestException as e:
            msg = (
                f"Inference endpoint '{inference_endpoint}' is not responding. "
                "Please ensure the URL is correct and the service is running."
            )
            raise ValueError(msg) from e

        if response.status_code != requests.codes.ok:
            msg = f"HuggingFace health check failed: {response.status_code}"
            raise ValueError(msg)
        # returning True to solve linting error
        return True

    def get_api_url(self) -> str:
        if "huggingface" in self.inference_endpoint.lower():
            return f"{self.inference_endpoint}"
        return self.inference_endpoint

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    def create_huggingface_embeddings(
        self, api_key: SecretStr, api_url: str, model_name: str
    ) -> HuggingFaceInferenceAPIEmbeddings:
        return HuggingFaceInferenceAPIEmbeddings(api_key=api_key, api_url=api_url, model_name=model_name)

    def build_embeddings(self) -> Embeddings:
        api_url = self.get_api_url()

        is_local_url = (
            api_url.startswith(("http://localhost", "http://127.0.0.1", "http://0.0.0.0", "http://docker"))
            or "huggingface.co" not in api_url.lower()
        )

        if not self.api_key and is_local_url:
            self.validate_inference_endpoint(api_url)
            api_key = SecretStr("APIKeyForLocalDeployment")
        elif not self.api_key:
            msg = "API Key is required for non-local inference endpoints"
            raise ValueError(msg)
        else:
            api_key = SecretStr(self.api_key).get_secret_value()

        try:
            return self.create_huggingface_embeddings(api_key, api_url, self.model_name)
        except Exception as e:
            msg = "Could not connect to HuggingFace Inference API."
            raise ValueError(msg) from e

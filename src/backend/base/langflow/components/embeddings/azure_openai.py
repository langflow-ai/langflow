"""Azure OpenAI embeddings component for Langflow.

This module provides the AzureOpenAIEmbeddingsComponent which integrates Azure's
OpenAI embedding models into Langflow workflows. Azure OpenAI provides the same
models as OpenAI but through Microsoft's Azure infrastructure with additional
enterprise features.

Key Features:
    - Enterprise-grade Azure OpenAI service integration
    - Support for all OpenAI embedding models via Azure endpoints
    - Configurable API versions for compatibility and feature access
    - Azure-specific authentication and endpoint configuration
    - Dimension control for supported embedding models

Supported Models (via Azure):
    - text-embedding-3-small: 1536 dimensions, improved performance
    - text-embedding-3-large: 3072 dimensions, highest quality
    - text-embedding-ada-002: 1536 dimensions, legacy model
    - text-embedding-ada-001: 1024 dimensions, deprecated

Azure Configuration:
    - azure_endpoint: Full Azure OpenAI resource URL
    - azure_deployment: Deployment name configured in Azure
    - api_version: Azure API version (supports multiple versions)
    - api_key: Azure OpenAI API key for authentication
    - dimensions: Optional embedding dimension override

API Versions Supported:
    - 2022-12-01: Initial GA version
    - 2023-03-15-preview: Preview with enhanced features
    - 2023-05-15: Stable release with improvements
    - 2023-06-01-preview: Preview with additional capabilities
    - 2023-07-01-preview: Latest preview features
    - 2023-08-01-preview: Most recent preview version

Enterprise Benefits:
    - Private network connectivity via Azure VNet
    - Compliance with enterprise security requirements
    - SLA guarantees and Azure support integration
    - Regional data residency options

The component wraps langchain_openai.AzureOpenAIEmbeddings and provides
Langflow-specific configuration and error handling.
"""

from langchain_openai import AzureOpenAIEmbeddings

from langflow.base.models.model import LCModelComponent
from langflow.base.models.openai_constants import OPENAI_EMBEDDING_MODEL_NAMES
from langflow.field_typing import Embeddings
from langflow.io import DropdownInput, IntInput, MessageTextInput, Output, SecretStrInput


class AzureOpenAIEmbeddingsComponent(LCModelComponent):
    display_name: str = "Azure OpenAI Embeddings"
    description: str = "Generate embeddings using Azure OpenAI models."
    documentation: str = "https://python.langchain.com/docs/integrations/text_embedding/azureopenai"
    icon = "Azure"
    name = "AzureOpenAIEmbeddings"

    API_VERSION_OPTIONS = [
        "2022-12-01",
        "2023-03-15-preview",
        "2023-05-15",
        "2023-06-01-preview",
        "2023-07-01-preview",
        "2023-08-01-preview",
    ]

    inputs = [
        DropdownInput(
            name="model",
            display_name="Model",
            advanced=False,
            options=OPENAI_EMBEDDING_MODEL_NAMES,
            value=OPENAI_EMBEDDING_MODEL_NAMES[0],
        ),
        MessageTextInput(
            name="azure_endpoint",
            display_name="Azure Endpoint",
            required=True,
            info="Your Azure endpoint, including the resource. Example: `https://example-resource.azure.openai.com/`",
        ),
        MessageTextInput(
            name="azure_deployment",
            display_name="Deployment Name",
            required=True,
        ),
        DropdownInput(
            name="api_version",
            display_name="API Version",
            options=API_VERSION_OPTIONS,
            value=API_VERSION_OPTIONS[-1],
            advanced=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            required=True,
        ),
        IntInput(
            name="dimensions",
            display_name="Dimensions",
            info="The number of dimensions the resulting output embeddings should have. "
            "Only supported by certain models.",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Embeddings", name="embeddings", method="build_embeddings"),
    ]

    def build_embeddings(self) -> Embeddings:
        try:
            embeddings = AzureOpenAIEmbeddings(
                model=self.model,
                azure_endpoint=self.azure_endpoint,
                azure_deployment=self.azure_deployment,
                api_version=self.api_version,
                api_key=self.api_key,
                dimensions=self.dimensions or None,
            )
        except Exception as e:
            msg = f"Could not connect to AzureOpenAIEmbeddings API: {e}"
            raise ValueError(msg) from e

        return embeddings

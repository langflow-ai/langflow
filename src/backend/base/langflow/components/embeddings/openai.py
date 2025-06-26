"""OpenAI embeddings component for Langflow.

This module provides the OpenAIEmbeddingsComponent which integrates OpenAI's
text embedding models into Langflow workflows for semantic search, clustering,
and similarity analysis.

Supported Models:
    Uses OpenAI's embedding models via langchain_openai.OpenAIEmbeddings:
    - text-embedding-3-small: 1536 dimensions, improved performance
    - text-embedding-3-large: 3072 dimensions, highest quality
    - text-embedding-ada-002: 1536 dimensions, legacy model
    - text-embedding-ada-001: 1024 dimensions, deprecated

Key Features:
    - Configurable embedding dimensions (for supported models)
    - Batch processing with chunk_size control
    - Progress bar display for large datasets
    - Custom headers and query parameters
    - TikToken integration for efficient tokenization
    - Proxy support for enterprise environments

Component Configuration:
    - API Key: Required OpenAI API key via SecretStrInput
    - Model Selection: Dropdown with supported model names
    - Chunk Size: Batch size for processing multiple texts
    - Dimensions: Output embedding size (model-dependent)
    - Timeout: Request timeout for API calls

The component wraps langchain_openai.OpenAIEmbeddings and provides
Langflow-specific input validation and error handling.
"""

from langchain_openai import OpenAIEmbeddings

from langflow.base.embeddings.model import LCEmbeddingsModel
from langflow.base.models.openai_constants import OPENAI_EMBEDDING_MODEL_NAMES
from langflow.field_typing import Embeddings
from langflow.io import BoolInput, DictInput, DropdownInput, FloatInput, IntInput, MessageTextInput, SecretStrInput


class OpenAIEmbeddingsComponent(LCEmbeddingsModel):
    display_name = "OpenAI Embeddings"
    description = "Generate embeddings using OpenAI models."
    icon = "OpenAI"
    name = "OpenAIEmbeddings"

    inputs = [
        DictInput(
            name="default_headers",
            display_name="Default Headers",
            advanced=True,
            info="Default headers to use for the API request.",
        ),
        DictInput(
            name="default_query",
            display_name="Default Query",
            advanced=True,
            info="Default query parameters to use for the API request.",
        ),
        IntInput(name="chunk_size", display_name="Chunk Size", advanced=True, value=1000),
        MessageTextInput(name="client", display_name="Client", advanced=True),
        MessageTextInput(name="deployment", display_name="Deployment", advanced=True),
        IntInput(name="embedding_ctx_length", display_name="Embedding Context Length", advanced=True, value=1536),
        IntInput(name="max_retries", display_name="Max Retries", value=3, advanced=True),
        DropdownInput(
            name="model",
            display_name="Model",
            advanced=False,
            options=OPENAI_EMBEDDING_MODEL_NAMES,
            value="text-embedding-3-small",
        ),
        DictInput(name="model_kwargs", display_name="Model Kwargs", advanced=True),
        SecretStrInput(name="openai_api_key", display_name="OpenAI API Key", value="OPENAI_API_KEY", required=True),
        MessageTextInput(name="openai_api_base", display_name="OpenAI API Base", advanced=True),
        MessageTextInput(name="openai_api_type", display_name="OpenAI API Type", advanced=True),
        MessageTextInput(name="openai_api_version", display_name="OpenAI API Version", advanced=True),
        MessageTextInput(
            name="openai_organization",
            display_name="OpenAI Organization",
            advanced=True,
        ),
        MessageTextInput(name="openai_proxy", display_name="OpenAI Proxy", advanced=True),
        FloatInput(name="request_timeout", display_name="Request Timeout", advanced=True),
        BoolInput(name="show_progress_bar", display_name="Show Progress Bar", advanced=True),
        BoolInput(name="skip_empty", display_name="Skip Empty", advanced=True),
        MessageTextInput(
            name="tiktoken_model_name",
            display_name="TikToken Model Name",
            advanced=True,
        ),
        BoolInput(
            name="tiktoken_enable",
            display_name="TikToken Enable",
            advanced=True,
            value=True,
            info="If False, you must have transformers installed.",
        ),
        IntInput(
            name="dimensions",
            display_name="Dimensions",
            info="The number of dimensions the resulting output embeddings should have. "
            "Only supported by certain models.",
            advanced=True,
        ),
    ]

    def build_embeddings(self) -> Embeddings:
        return OpenAIEmbeddings(
            client=self.client or None,
            model=self.model,
            dimensions=self.dimensions or None,
            deployment=self.deployment or None,
            api_version=self.openai_api_version or None,
            base_url=self.openai_api_base or None,
            openai_api_type=self.openai_api_type or None,
            openai_proxy=self.openai_proxy or None,
            embedding_ctx_length=self.embedding_ctx_length,
            api_key=self.openai_api_key or None,
            organization=self.openai_organization or None,
            allowed_special="all",
            disallowed_special="all",
            chunk_size=self.chunk_size,
            max_retries=self.max_retries,
            timeout=self.request_timeout or None,
            tiktoken_enabled=self.tiktoken_enable,
            tiktoken_model_name=self.tiktoken_model_name or None,
            show_progress_bar=self.show_progress_bar,
            model_kwargs=self.model_kwargs,
            skip_empty=self.skip_empty,
            default_headers=self.default_headers or None,
            default_query=self.default_query or None,
        )

"""Cohere embeddings component for Langflow.

This module provides the CohereEmbeddingsComponent which integrates Cohere's
embedding models into Langflow workflows. Cohere offers multilingual embeddings
optimized for various text analysis tasks.

Supported Models:
    - embed-english-v2.0: Latest English-only model with improved performance
    - embed-multilingual-v2.0: Multilingual model supporting 100+ languages
    - embed-english-light-v2.0: Lightweight English model for faster inference
    - embed-multilingual-light-v2.0: Lightweight multilingual model

Key Features:
    - Multilingual support with high-quality embeddings
    - Dynamic model fetching from Cohere API
    - Configurable truncation strategies
    - Retry mechanisms for reliability
    - Custom user-agent and timeout settings

Configuration Options:
    - api_key: Required Cohere API key with real-time refresh
    - model_name: Dropdown with available models (refreshable)
    - truncate: Text truncation strategy ("NONE", "START", "END")
    - max_retries: Number of retry attempts for failed requests
    - user_agent: Custom user agent string for API calls
    - request_timeout: Timeout for API requests in seconds

Multilingual Capabilities:
    The multilingual models support:
    - 100+ languages with high-quality embeddings
    - Cross-lingual semantic similarity
    - Code-switching and mixed-language text
    - Consistent embedding space across languages

Performance Characteristics:
    - Standard models: Higher accuracy, larger size
    - Light models: 50% smaller, faster inference
    - Optimized for semantic search and clustering
    - Efficient batch processing support

The component uses langchain_cohere.CohereEmbeddings and provides dynamic
model discovery with real-time API integration.
"""

from typing import Any

import cohere
from langchain_cohere import CohereEmbeddings

from langflow.base.models.model import LCModelComponent
from langflow.field_typing import Embeddings
from langflow.io import DropdownInput, FloatInput, IntInput, MessageTextInput, Output, SecretStrInput

HTTP_STATUS_OK = 200


class CohereEmbeddingsComponent(LCModelComponent):
    display_name = "Cohere Embeddings"
    description = "Generate embeddings using Cohere models."
    icon = "Cohere"
    name = "CohereEmbeddings"

    inputs = [
        SecretStrInput(name="api_key", display_name="Cohere API Key", required=True, real_time_refresh=True),
        DropdownInput(
            name="model_name",
            display_name="Model",
            advanced=False,
            options=[
                "embed-english-v2.0",
                "embed-multilingual-v2.0",
                "embed-english-light-v2.0",
                "embed-multilingual-light-v2.0",
            ],
            value="embed-english-v2.0",
            refresh_button=True,
            combobox=True,
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
        data = None
        try:
            data = CohereEmbeddings(
                cohere_api_key=self.api_key,
                model=self.model_name,
                truncate=self.truncate,
                max_retries=self.max_retries,
                user_agent=self.user_agent,
                request_timeout=self.request_timeout or None,
            )
        except Exception as e:
            msg = (
                "Unable to create Cohere Embeddings. ",
                "Please verify the API key and model parameters, and try again.",
            )
            raise ValueError(msg) from e
        # added status if not the return data would be serialised to create the status
        return data

    def get_model(self):
        try:
            co = cohere.ClientV2(self.api_key)
            response = co.models.list(endpoint="embed")
            models = response.models
            return [model.name for model in models]
        except Exception as e:
            msg = f"Failed to fetch Cohere models. Error: {e}"
            raise ValueError(msg) from e

    async def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None):
        if field_name in {"model_name", "api_key"}:
            if build_config.get("api_key", {}).get("value", None):
                build_config["model_name"]["options"] = self.get_model()
        else:
            build_config["model_name"]["options"] = field_value
        return build_config

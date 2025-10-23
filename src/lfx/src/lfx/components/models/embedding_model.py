from typing import Any

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_ibm import WatsonxEmbeddings
from langchain_ollama import OllamaEmbeddings
from langchain_openai import OpenAIEmbeddings

from lfx.base.embeddings.model import LCEmbeddingsModel
from lfx.base.models.openai_constants import OPENAI_EMBEDDING_MODEL_NAMES
from lfx.field_typing import Embeddings
from lfx.io import (
    BoolInput,
    DictInput,
    FloatInput,
    IntInput,
    MessageTextInput,
    ModelInput,
    SecretStrInput,
)

# Mapping of class names to actual class objects
EMBEDDING_CLASSES = {
    "GoogleGenerativeAIEmbeddings": GoogleGenerativeAIEmbeddings,
    "OpenAIEmbeddings": OpenAIEmbeddings,
    "OllamaEmbeddings": OllamaEmbeddings,
    "WatsonxEmbeddings": WatsonxEmbeddings,
}


def _get_embedding_model_options() -> list[dict[str, Any]]:
    """Return a list of available embedding model providers with their configuration."""
    openai_options = [
        {
            "name": model_name,
            "icon": "OpenAI",
            "category": "OpenAI",
            "provider": "OpenAI",
            "metadata": {
                "embedding_class": "OpenAIEmbeddings",
                "param_mapping": {
                    "model": "model",
                    "api_key": "api_key",
                    "api_base": "base_url",
                    "dimensions": "dimensions",
                    "chunk_size": "chunk_size",
                    "request_timeout": "request_timeout",
                    "max_retries": "max_retries",
                    "show_progress_bar": "show_progress_bar",
                    "model_kwargs": "model_kwargs",
                },
            },
        }
        for model_name in OPENAI_EMBEDDING_MODEL_NAMES
    ]

    google_options = [
        {
            "name": "GoogleGenerativeAIEmbeddings",
            "icon": "GoogleGenerativeAI",
            "category": "Google",
            "provider": "Google",
            "metadata": {
                "embedding_class": "GoogleGenerativeAIEmbeddings",
                "param_mapping": {
                    "model": "model",
                    "api_key": "google_api_key",
                    "request_timeout": "request_options",
                    "model_kwargs": "client_options",
                },
            },
        }
    ]

    ollama_options = [
        {
            "name": "OllamaEmbeddings",
            "icon": "Ollama",
            "category": "Ollama",
            "provider": "Ollama",
            "metadata": {
                "embedding_class": "OllamaEmbeddings",
                "param_mapping": {
                    "model": "model",
                    "base_url": "base_url",
                    "num_ctx": "num_ctx",
                    "request_timeout": "request_timeout",
                    "model_kwargs": "model_kwargs",
                },
            },
        }
    ]

    watsonx_options = [
        {
            "name": "WatsonxEmbeddings",
            "icon": "WatsonxAI",
            "category": "IBM WatsonX",
            "provider": "IBM WatsonX",
            "metadata": {
                "embedding_class": "WatsonxEmbeddings",
                "param_mapping": {
                    "model_id": "model_id",
                    "url": "url",
                    "api_key": "apikey",
                    "project_id": "project_id",
                    "space_id": "space_id",
                    "request_timeout": "request_timeout",
                },
            },
        }
    ]

    return openai_options + google_options + ollama_options + watsonx_options


# Compute model options once at module level
_MODEL_OPTIONS = _get_embedding_model_options()
_PROVIDERS = [option["provider"] for option in _MODEL_OPTIONS]


class EmbeddingModelComponent(LCEmbeddingsModel):
    display_name = "Embedding Model"
    description = "Generate embeddings using a specified provider."
    documentation: str = "https://docs.langflow.org/components-embedding-models"
    icon = "binary"
    name = "EmbeddingModel"
    category = "models"

    inputs = [
        ModelInput(
            name="model",
            display_name="Embedding Model",
            model_options=_MODEL_OPTIONS,
            providers=_PROVIDERS,
            info="Select your model provider",
            real_time_refresh=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info="Model Provider API key",
            required=True,
            show=True,
            real_time_refresh=True,
        ),
        MessageTextInput(
            name="api_base",
            display_name="API Base URL",
            info="Base URL for the API. Leave empty for default.",
            advanced=True,
        ),
        IntInput(
            name="dimensions",
            display_name="Dimensions",
            info="The number of dimensions the resulting output embeddings should have. "
            "Only supported by certain models.",
            advanced=True,
        ),
        IntInput(
            name="chunk_size",
            display_name="Chunk Size",
            advanced=True,
            value=1000,
        ),
        FloatInput(
            name="request_timeout",
            display_name="Request Timeout",
            advanced=True,
        ),
        IntInput(
            name="max_retries",
            display_name="Max Retries",
            advanced=True,
            value=3,
        ),
        BoolInput(
            name="show_progress_bar",
            display_name="Show Progress Bar",
            advanced=True,
        ),
        DictInput(
            name="model_kwargs",
            display_name="Model Kwargs",
            advanced=True,
            info="Additional keyword arguments to pass to the model.",
        ),
    ]

    def build_embeddings(self) -> Embeddings:
        """Build and return an embeddings instance based on the selected model."""
        # Safely extract model configuration
        if not self.model or not isinstance(self.model, list):
            msg = "Model must be a non-empty list"
            raise ValueError(msg)

        model = self.model[0]
        model_name = model.get("name")
        provider = model.get("provider")
        metadata = model.get("metadata", {})

        # Validate required fields
        if not self.api_key:
            msg = f"{provider} API key is required"
            raise ValueError(msg)

        if not model_name:
            msg = "Model name is required"
            raise ValueError(msg)

        # Get embedding class
        embedding_class_name = metadata.get("embedding_class")
        if not embedding_class_name:
            msg = f"No embedding class defined in metadata for {model_name}"
            raise ValueError(msg)

        embedding_class = EMBEDDING_CLASSES.get(embedding_class_name)
        if not embedding_class:
            msg = f"Unknown embedding class: {embedding_class_name}"
            raise ValueError(msg)

        # Build kwargs using parameter mapping
        kwargs = self._build_kwargs(model, metadata)

        return embedding_class(**kwargs)

    def _build_kwargs(self, model: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
        """Build kwargs dictionary using parameter mapping."""
        param_mapping = metadata.get("param_mapping", {})
        if not param_mapping:
            msg = "Parameter mapping not found in metadata"
            raise ValueError(msg)

        kwargs = {}

        # Required parameters
        if "model" in param_mapping:
            kwargs[param_mapping["model"]] = model.get("name")
        if "api_key" in param_mapping:
            kwargs[param_mapping["api_key"]] = self.api_key

        # Optional parameters with their values
        optional_params = {
            "api_base": self.api_base,
            "dimensions": int(self.dimensions) if self.dimensions else None,
            "chunk_size": int(self.chunk_size) if self.chunk_size else None,
            "request_timeout": float(self.request_timeout) if self.request_timeout else None,
            "max_retries": int(self.max_retries) if self.max_retries else None,
            "show_progress_bar": self.show_progress_bar if hasattr(self, "show_progress_bar") else None,
            "model_kwargs": self.model_kwargs,
        }

        # Add optional parameters if they have values and are mapped
        for param_name, param_value in optional_params.items():
            if param_value is not None and param_name in param_mapping:
                # Special handling for request_timeout with Google provider
                if param_name == "request_timeout":
                    provider = model.get("provider")
                    if provider == "Google" and isinstance(param_value, (int, float)):
                        kwargs[param_mapping[param_name]] = {"timeout": param_value}
                    else:
                        kwargs[param_mapping[param_name]] = param_value
                else:
                    kwargs[param_mapping[param_name]] = param_value

        return kwargs

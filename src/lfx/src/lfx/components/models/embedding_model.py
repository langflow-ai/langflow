from typing import Any

from lfx.base.embeddings.model import LCEmbeddingsModel
from lfx.base.models.unified_models import get_api_key_for_provider, get_embedding_classes, get_embedding_model_options
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


class EmbeddingModelComponent(LCEmbeddingsModel):
    display_name = "Embedding Model"
    description = "Generate embeddings using a specified provider."
    documentation: str = "https://docs.langflow.org/components-embedding-models"
    icon = "binary"
    name = "EmbeddingModel"
    category = "models"

    def update_build_config(self, build_config: dict, field_value: any, field_name: str | None = None):
        """Dynamically update build config with user-filtered model options."""
        # Fetch options based on user's enabled models and providers
        try:
            options = get_embedding_model_options(user_id=self.user_id)
            providers = list({opt["provider"] for opt in options})
            build_config["model"]["options"] = options
            build_config["model"]["providers"] = providers
        except Exception:
            # If we can't get user-specific options, fall back to empty
            pass
        return build_config

    inputs = [
        ModelInput(
            name="model",
            display_name="Embedding Model",
            options=[],  # Will be populated dynamically
            providers=[],  # Will be populated dynamically
            info="Select your model provider",
            real_time_refresh=True,
            refresh_button=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info="Model Provider API key",
            real_time_refresh=True,
            advanced=True,
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

        # Get API key from user input or global variables
        api_key = get_api_key_for_provider(self.user_id, provider, self.api_key)

        # Validate required fields (Ollama doesn't require API key)
        if not api_key and provider != "Ollama":
            msg = (
                f"{provider} API key is required. "
                f"Please provide it in the component or configure it globally as "
                f"{provider.upper().replace(' ', '_')}_API_KEY."
            )
            raise ValueError(msg)

        if not model_name:
            msg = "Model name is required"
            raise ValueError(msg)

        # Get embedding class
        embedding_class_name = metadata.get("embedding_class")
        if not embedding_class_name:
            msg = f"No embedding class defined in metadata for {model_name}"
            raise ValueError(msg)

        embedding_class = get_embedding_classes().get(embedding_class_name)
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
            kwargs[param_mapping["api_key"]] = get_api_key_for_provider(
                self.user_id,
                model.get("provider"),
                self.api_key,
            )

        # Optional parameters with their values
        optional_params = {
            "api_base": self.api_base if self.api_base else None,
            "dimensions": int(self.dimensions) if self.dimensions else None,
            "chunk_size": int(self.chunk_size) if self.chunk_size else None,
            "request_timeout": float(self.request_timeout) if self.request_timeout else None,
            "max_retries": int(self.max_retries) if self.max_retries else None,
            "show_progress_bar": self.show_progress_bar if hasattr(self, "show_progress_bar") else None,
            "model_kwargs": self.model_kwargs if self.model_kwargs else None,
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

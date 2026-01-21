from typing import Any

from lfx.base.embeddings.embeddings_class import EmbeddingsWithModels
from lfx.base.embeddings.model import LCEmbeddingsModel
from lfx.base.models.unified_models import (
    get_api_key_for_provider,
    get_embedding_classes,
    get_embedding_model_options,
    get_unified_models_detailed,
    update_model_options_in_build_config,
)
from lfx.base.models.watsonx_constants import IBM_WATSONX_URLS
from lfx.field_typing import Embeddings
from lfx.io import (
    BoolInput,
    DictInput,
    DropdownInput,
    FloatInput,
    IntInput,
    MessageTextInput,
    ModelInput,
    SecretStrInput,
)
from lfx.log.logger import logger


class EmbeddingModelComponent(LCEmbeddingsModel):
    display_name = "Embedding Model"
    description = "Generate embeddings using a specified provider."
    documentation: str = "https://docs.langflow.org/components-embedding-models"
    icon = "binary"
    name = "EmbeddingModel"
    category = "models"

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None):
        """Dynamically update build config with user-filtered model options."""
        # Update model options
        build_config = update_model_options_in_build_config(
            component=self,
            build_config=build_config,
            cache_key_prefix="embedding_model_options",
            get_options_func=get_embedding_model_options,
            field_name=field_name,
            field_value=field_value,
        )

        # Show/hide provider-specific fields based on selected model
        if field_name == "model" and isinstance(field_value, list) and len(field_value) > 0:
            selected_model = field_value[0]
            provider = selected_model.get("provider", "")

            # Show/hide watsonx fields
            is_watsonx = provider == "IBM WatsonX"
            build_config["base_url_ibm_watsonx"]["show"] = is_watsonx
            build_config["project_id"]["show"] = is_watsonx
            build_config["truncate_input_tokens"]["show"] = is_watsonx
            build_config["input_text"]["show"] = is_watsonx
            if is_watsonx:
                build_config["base_url_ibm_watsonx"]["required"] = True
                build_config["project_id"]["required"] = True

        return build_config

    inputs = [
        ModelInput(
            name="model",
            display_name="Embedding Model",
            info="Select your model provider",
            real_time_refresh=True,
            required=True,
            model_type="embedding",
            input_types=["Embeddings"],  # Override default to accept Embeddings instead of LanguageModel
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
        # Watson-specific inputs
        DropdownInput(
            name="base_url_ibm_watsonx",
            display_name="watsonx API Endpoint",
            info="The base URL of the API (IBM watsonx.ai only)",
            options=IBM_WATSONX_URLS,
            value=IBM_WATSONX_URLS[0],
            show=False,
            real_time_refresh=True,
        ),
        MessageTextInput(
            name="project_id",
            display_name="Project ID",
            info="IBM watsonx.ai Project ID (required for IBM watsonx.ai)",
            show=False,
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
        IntInput(
            name="truncate_input_tokens",
            display_name="Truncate Input Tokens",
            advanced=True,
            value=200,
            show=False,
        ),
        BoolInput(
            name="input_text",
            display_name="Include the original text in the output",
            value=True,
            advanced=True,
            show=False,
        ),
    ]

    def build_embeddings(self) -> Embeddings:
        """Build and return an embeddings instance based on the selected model.

        Returns an EmbeddingsWithModels wrapper that contains:
        - The primary embedding instance (for the selected model)
        - available_models dict mapping all available model names to their instances
        """
        # If an Embeddings object is directly connected, return it
        try:
            from langchain_core.embeddings import Embeddings as BaseEmbeddings

            if isinstance(self.model, BaseEmbeddings):
                return self.model
        except ImportError:
            pass

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

        # Build kwargs using parameter mapping for primary instance
        kwargs = self._build_kwargs(model, metadata)
        primary_instance = embedding_class(**kwargs)

        # Get all available embedding models for this provider
        available_models_dict = self._build_available_models(
            provider=provider,
            embedding_class=embedding_class,
            metadata=metadata,
            api_key=api_key,
        )

        # Wrap with EmbeddingsWithModels to provide available_models metadata
        return EmbeddingsWithModels(
            embeddings=primary_instance,
            available_models=available_models_dict,
        )

    def _build_available_models(
        self,
        provider: str,
        embedding_class: type,
        metadata: dict[str, Any],
        api_key: str | None,
    ) -> dict[str, Embeddings]:
        """Build a dictionary of all available embedding model instances for the provider.

        Args:
            provider: The provider name (e.g., "OpenAI", "Ollama")
            embedding_class: The embedding class to instantiate
            metadata: Metadata containing param_mapping
            api_key: The API key for the provider

        Returns:
            Dict mapping model names to their embedding instances
        """
        available_models_dict: dict[str, Embeddings] = {}

        # Get all embedding models for this provider from unified models
        all_embedding_models = get_unified_models_detailed(
            providers=[provider],
            model_type="embeddings",
            include_deprecated=False,
            include_unsupported=False,
        )

        if not all_embedding_models:
            return available_models_dict

        # Extract models from the provider data
        for provider_data in all_embedding_models:
            if provider_data.get("provider") != provider:
                continue

            for model_data in provider_data.get("models", []):
                model_name = model_data.get("model_name")
                if not model_name:
                    continue

                # Create a model dict compatible with _build_kwargs
                model_dict = {
                    "name": model_name,
                    "provider": provider,
                    "metadata": metadata,  # Reuse the same metadata/param_mapping
                }

                try:
                    # Build kwargs for this model
                    model_kwargs = self._build_kwargs_for_model(model_dict, metadata, api_key)
                    # Create the embedding instance
                    available_models_dict[model_name] = embedding_class(**model_kwargs)
                except Exception:  # noqa: BLE001
                    # Skip models that fail to instantiate
                    # This handles cases where specific models have incompatible parameters
                    logger.debug("Failed to instantiate embedding model %s: skipping", model_name, exc_info=True)
                    continue

        return available_models_dict

    def _build_kwargs_for_model(
        self,
        model: dict[str, Any],
        metadata: dict[str, Any],
        api_key: str | None,
    ) -> dict[str, Any]:
        """Build kwargs dictionary for a specific model using parameter mapping.

        This is similar to _build_kwargs but uses the provided api_key directly
        instead of looking it up again.

        Args:
            model: Model dict with name and provider
            metadata: Metadata containing param_mapping
            api_key: The API key to use

        Returns:
            kwargs dict for embedding class instantiation
        """
        param_mapping = metadata.get("param_mapping", {})
        if not param_mapping:
            msg = "Parameter mapping not found in metadata"
            raise ValueError(msg)

        kwargs = {}
        provider = model.get("provider")

        # Required parameters - handle both "model" and "model_id" (for watsonx)
        if "model" in param_mapping:
            kwargs[param_mapping["model"]] = model.get("name")
        elif "model_id" in param_mapping:
            kwargs[param_mapping["model_id"]] = model.get("name")

        # Add API key if mapped
        if "api_key" in param_mapping and api_key:
            kwargs[param_mapping["api_key"]] = api_key

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

        # Watson-specific parameters
        if provider in {"IBM WatsonX", "IBM watsonx.ai"}:
            # Map base_url_ibm_watsonx to "url" parameter for watsonx
            if "url" in param_mapping:
                url_value = (
                    self.base_url_ibm_watsonx
                    if hasattr(self, "base_url_ibm_watsonx") and self.base_url_ibm_watsonx
                    else "https://us-south.ml.cloud.ibm.com"
                )
                kwargs[param_mapping["url"]] = url_value
            # Map project_id for watsonx
            if hasattr(self, "project_id") and self.project_id and "project_id" in param_mapping:
                kwargs[param_mapping["project_id"]] = self.project_id

        # Ollama-specific parameters
        if provider == "Ollama" and "base_url" in param_mapping:
            # Map api_base to "base_url" parameter for Ollama
            base_url_value = self.api_base if hasattr(self, "api_base") and self.api_base else "http://localhost:11434"
            kwargs[param_mapping["base_url"]] = base_url_value

        # Add optional parameters if they have values and are mapped
        for param_name, param_value in optional_params.items():
            if param_value is not None and param_name in param_mapping:
                # Special handling for request_timeout with Google provider
                if param_name == "request_timeout":
                    if provider == "Google Generative AI" and isinstance(param_value, (int, float)):
                        kwargs[param_mapping[param_name]] = {"timeout": param_value}
                    else:
                        kwargs[param_mapping[param_name]] = param_value
                else:
                    kwargs[param_mapping[param_name]] = param_value

        return kwargs

    def _build_kwargs(self, model: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
        """Build kwargs dictionary using parameter mapping."""
        param_mapping = metadata.get("param_mapping", {})
        if not param_mapping:
            msg = "Parameter mapping not found in metadata"
            raise ValueError(msg)

        kwargs = {}

        # Required parameters - handle both "model" and "model_id" (for watsonx)
        if "model" in param_mapping:
            kwargs[param_mapping["model"]] = model.get("name")
        elif "model_id" in param_mapping:
            kwargs[param_mapping["model_id"]] = model.get("name")
        if "api_key" in param_mapping:
            kwargs[param_mapping["api_key"]] = get_api_key_for_provider(
                self.user_id,
                model.get("provider"),
                self.api_key,
            )

        # Optional parameters with their values
        provider = model.get("provider")
        optional_params = {
            "api_base": self.api_base if self.api_base else None,
            "dimensions": int(self.dimensions) if self.dimensions else None,
            "chunk_size": int(self.chunk_size) if self.chunk_size else None,
            "request_timeout": float(self.request_timeout) if self.request_timeout else None,
            "max_retries": int(self.max_retries) if self.max_retries else None,
            "show_progress_bar": self.show_progress_bar if hasattr(self, "show_progress_bar") else None,
            "model_kwargs": self.model_kwargs if self.model_kwargs else None,
        }

        # Watson-specific parameters
        if provider in {"IBM WatsonX", "IBM watsonx.ai"}:
            # Map base_url_ibm_watsonx to "url" parameter for watsonx
            if "url" in param_mapping:
                url_value = (
                    self.base_url_ibm_watsonx
                    if hasattr(self, "base_url_ibm_watsonx") and self.base_url_ibm_watsonx
                    else "https://us-south.ml.cloud.ibm.com"
                )
                kwargs[param_mapping["url"]] = url_value
            # Map project_id for watsonx
            if hasattr(self, "project_id") and self.project_id and "project_id" in param_mapping:
                kwargs[param_mapping["project_id"]] = self.project_id

        # Ollama-specific parameters
        if provider == "Ollama" and "base_url" in param_mapping:
            # Map api_base to "base_url" parameter for Ollama
            base_url_value = self.api_base if hasattr(self, "api_base") and self.api_base else "http://localhost:11434"
            kwargs[param_mapping["base_url"]] = base_url_value

        # Add optional parameters if they have values and are mapped
        for param_name, param_value in optional_params.items():
            if param_value is not None and param_name in param_mapping:
                # Special handling for request_timeout with Google provider
                if param_name == "request_timeout":
                    if provider == "Google Generative AI" and isinstance(param_value, (int, float)):
                        kwargs[param_mapping[param_name]] = {"timeout": param_value}
                    else:
                        kwargs[param_mapping[param_name]] = param_value
                else:
                    kwargs[param_mapping[param_name]] = param_value

        return kwargs

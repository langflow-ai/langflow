from typing import Any

from langchain_openai import OpenAIEmbeddings

from langflow.custom.custom_component.component import Component
from langflow.field_typing import Embeddings
from langflow.inputs.inputs import ModelInput
from langflow.io import SecretStrInput
from langflow.schema.dotdict import dotdict
from langflow.template.field.base import Output


class UnifiedEmbeddingModelComponent(Component):
    display_name = "Unified Embedding Model"
    description = "A unified embedding model component that supports OpenAI embedding models using the new ModelInput."
    documentation: str = "https://docs.langflow.org/components-models"
    icon = "brain-circuit"
    category = "models"
    priority = 2

    inputs = [
        ModelInput(
            name="model_selection",
            display_name="Embedding Model",
            info="Select the embedding model to use",
            model_type="embedding",
            value="OpenAI:text-embedding-3-small",
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info="The API key for the selected provider",
            required=False,
            real_time_refresh=True,
        ),
    ]

    outputs = [
        Output(display_name="Embeddings", name="embeddings_output", method="build_embeddings"),
    ]

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None) -> dotdict:
        """Update the build configuration based on field changes."""
        if field_name == "model_selection" and isinstance(field_value, str) and ":" in field_value:
            # Parse Provider:ModelName format
            provider = field_value.split(":", 1)[0].strip()

            # Update API key display name based on provider
            if provider == "OpenAI":
                build_config["api_key"]["display_name"] = "OpenAI API Key"
                build_config["api_key"]["info"] = "Your OpenAI API key"
            else:
                build_config["api_key"]["display_name"] = "API Key"
                build_config["api_key"]["info"] = "The API key for the selected provider"

        return build_config

    def build_embeddings(self) -> Embeddings:
        """Build the embedding model based on the selected provider and configuration."""
        model_selection = self.model_selection

        if not isinstance(model_selection, str):
            msg = "Model selection must be a string in 'Provider:ModelName' format"
            raise TypeError(msg)

        if not model_selection or ":" not in model_selection:
            msg = "Model selection must be in 'Provider:ModelName' format"
            raise ValueError(msg)

        # Parse the selection
        provider, model_name = model_selection.split(":", 1)
        provider = provider.strip()
        model_name = model_name.strip()

        if not provider or not model_name:
            msg = "Both provider and model name must be specified"
            raise ValueError(msg)

        # Build embedding model based on provider
        if provider == "OpenAI":
            return OpenAIEmbeddings(
                openai_api_key=self.api_key,
                model=model_name,
            )

        msg = f"Unsupported provider: {provider}. Currently only OpenAI is supported for embeddings"
        raise ValueError(msg)

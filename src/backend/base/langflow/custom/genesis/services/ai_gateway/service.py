"""AI Gateway Service for Genesis Studio."""

from __future__ import annotations

from typing import Any

from loguru import logger

# SDK imports
from modelhub.clients import AIGatewayClient

from langflow.services.base import Service

from .settings import AIGatewaySettings


class AIGatewayService(Service):
    """Service for AI Gateway operations using admin key for model discovery and user API keys for chat."""

    name = "ai_gateway_service"

    def __init__(self):
        super().__init__()
        self.settings = AIGatewaySettings()
        self._ready = False
        self._provider_models = {}  # provider -> list of model_names
        self._model_name_to_base_model = {}  # model_name -> base_model (part after slash)
        self._models_synced = False

    def set_ready(self) -> None:
        """Set the service as ready."""
        self._ready = True

    @property
    def ready(self) -> bool:
        """Check if the service is ready."""
        return self._ready

    async def cleanup(self) -> None:
        """Cleanup resources."""

    def sync_models(self) -> dict[str, list[str]]:
        """Sync models from AI Gateway using admin key."""
        client = AIGatewayClient(virtual_key=self.settings.ADMIN_KEY)

        # Fetch models using /model/info endpoint
        logger.info("Fetching models from AI Gateway...")
        models_response = client.request("GET", "/model/info")

        # Parse response and build provider -> model_names mapping
        self._provider_models = {}
        self._model_name_to_base_model = {}
        if "data" in models_response and isinstance(models_response["data"], list):
            for model_data in models_response["data"]:
                if (
                    "model_name" in model_data
                    and "litellm_params" in model_data
                    and model_data["litellm_params"] is not None
                    and "model" in model_data["litellm_params"]
                ):
                    model_name = model_data["model_name"]
                    litellm_model = model_data["litellm_params"]["model"]

                    # Extract provider and base model
                    if "/" in litellm_model:
                        provider, base_model = litellm_model.split("/", 1)
                        if provider not in self._provider_models:
                            self._provider_models[provider] = []
                        self._provider_models[provider].append(model_name)
                        self._model_name_to_base_model[model_name] = base_model

        self._models_synced = True
        logger.info(
            f"Successfully synced {len(self._provider_models)} providers with "
            f"{len(self._model_name_to_base_model)} model names"
        )
        return self._provider_models

    def _ensure_models_synced(self) -> None:
        """Ensure models are synced before accessing them."""
        if not self._models_synced:
            self.sync_models()

    def get_providers(self) -> list[str]:
        """Get available providers."""
        self._ensure_models_synced()
        return list(self._provider_models.keys())

    def get_models(self, provider: str) -> list[str]:
        """Get model names for provider."""
        self._ensure_models_synced()
        return self._provider_models.get(provider, [])

    def get_base_model(self, model_name: str) -> str:
        """Get base model for a given model name."""
        self._ensure_models_synced()
        return self._model_name_to_base_model.get(model_name, "")

    def chat_completion(
        self,
        model_name: str,
        messages: list[dict[str, str]],
        api_key: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> dict[str, Any]:
        """Execute chat completion using user API key and model name directly."""
        client = AIGatewayClient(virtual_key=api_key)

        # Use the model_name directly from the API response (e.g., "Test GPT-4o")
        # The API key permissions determine which model it can access
        payload = {"model": model_name, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
        return client.request("POST", "/v1/chat/completions", json=payload)

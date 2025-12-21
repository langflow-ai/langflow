from typing import Any
from urllib.parse import urljoin

import httpx
from langchain_ollama import OllamaEmbeddings

from lfx.base.models.model import LCModelComponent
from lfx.field_typing import Embeddings
from lfx.io import DropdownInput, MessageTextInput, Output
from lfx.utils.util import transform_localhost_url

HTTP_STATUS_OK = 200


class OllamaEmbeddingsComponent(LCModelComponent):
    display_name: str = "Ollama Embeddings"
    description: str = "Generate embeddings using Ollama models."
    documentation = "https://python.langchain.com/docs/integrations/text_embedding/ollama"
    icon = "Ollama"
    name = "OllamaEmbeddings"

    inputs = [
        DropdownInput(
            name="model_name",
            display_name="Ollama Model",
            value="",
            options=[],
            real_time_refresh=True,
            refresh_button=True,
            combobox=True,
            required=True,
        ),
        MessageTextInput(
            name="base_url",
            display_name="Ollama Base URL",
            value="",
            required=True,
        ),
    ]

    outputs = [
        Output(display_name="Embeddings", name="embeddings", method="build_embeddings"),
    ]

    def build_embeddings(self) -> Embeddings:
        """Build and return an OllamaEmbeddings instance.

        Returns:
            Embeddings: An OllamaEmbeddings instance configured with the specified model and base URL.

        Raises:
            ValueError: If unable to connect to the Ollama API or if the model is not available.
        """
        transformed_base_url = transform_localhost_url(self.base_url)
        try:
            output = OllamaEmbeddings(model=self.model_name, base_url=transformed_base_url)
        except Exception as e:
            msg = (
                "Unable to connect to the Ollama API. ",
                "Please verify the base URL, ensure the relevant Ollama model is pulled, and try again.",
            )
            raise ValueError(msg) from e
        return output

    async def update_build_config(self, build_config: dict, _field_value: Any, field_name: str | None = None):
        """Update the build configuration based on field changes.

        Args:
            build_config: The current build configuration dictionary.
            _field_value: The new value of the field (unused).
            field_name: The name of the field that was changed.

        Returns:
            dict: The updated build configuration.

        Raises:
            ValueError: If the Ollama base URL is invalid or Ollama is not running.
        """
        if field_name in {"base_url", "model_name"} and not await self.is_valid_ollama_url(self.base_url):
            msg = "Ollama is not running on the provided base URL. Please start Ollama and try again."
            raise ValueError(msg)
        if field_name in {"model_name", "base_url", "tool_model_enabled"}:
            if await self.is_valid_ollama_url(self.base_url):
                build_config["model_name"]["options"] = await self.get_model(self.base_url)
            else:
                build_config["model_name"]["options"] = []

        return build_config

    async def get_model(self, base_url_value: str) -> list[str]:
        """Get the model names from Ollama.

        Fetches all available models from the Ollama API and returns their names.
        This method returns all models without filtering, allowing users to select
        any model including custom ones.

        Args:
            base_url_value: The base URL of the Ollama API instance.

        Returns:
            list[str]: A list of model names available in Ollama.

        Raises:
            ValueError: If unable to connect to Ollama or parse the response.
        """
        model_ids = []
        try:
            base_url_value = transform_localhost_url(base_url_value)
            url = urljoin(base_url_value, "/api/tags")
            async with httpx.AsyncClient() as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()

            model_ids = [model["name"] for model in data.get("models", [])]
            # Return all available models from Ollama.
            # Ollama supports custom embedding models and models with various naming conventions
            # (e.g., gemma3:4b, deepseek-r1:8b), so we show all models and let users choose.
            # The Ollama API will handle validation when the model is actually used.

        except (ImportError, ValueError, httpx.RequestError) as e:
            msg = "Could not get model names from Ollama."
            raise ValueError(msg) from e

        return model_ids

    async def is_valid_ollama_url(self, url: str) -> bool:
        """Check if the provided URL is a valid Ollama instance.

        Args:
            url: The URL to validate.

        Returns:
            bool: True if the URL points to a valid Ollama instance, False otherwise.
        """
        try:
            async with httpx.AsyncClient() as client:
                url = transform_localhost_url(url)
                return (await client.get(f"{url}/api/tags")).status_code == HTTP_STATUS_OK
        except httpx.RequestError:
            return False

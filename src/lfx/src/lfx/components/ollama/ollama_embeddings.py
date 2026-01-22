import asyncio
from typing import Any
from urllib.parse import urljoin

import httpx
from langchain_ollama import OllamaEmbeddings

from lfx.base.models.model import LCModelComponent
from lfx.field_typing import Embeddings
from lfx.io import DropdownInput, MessageTextInput, Output, SecretStrInput
from lfx.log.logger import logger
from lfx.utils.util import transform_localhost_url

HTTP_STATUS_OK = 200


class OllamaEmbeddingsComponent(LCModelComponent):
    display_name: str = "Ollama Embeddings"
    description: str = "Generate embeddings using Ollama models."
    documentation = "https://python.langchain.com/docs/integrations/text_embedding/ollama"
    icon = "Ollama"
    name = "OllamaEmbeddings"

    # Define constants for JSON keys
    JSON_MODELS_KEY = "models"
    JSON_NAME_KEY = "name"
    JSON_CAPABILITIES_KEY = "capabilities"
    EMBEDDING_CAPABILITY = "embedding"

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
            info="Endpoint of the Ollama API. Defaults to http://localhost:11434.",
            value="http://localhost:11434",
            required=True,
            real_time_refresh=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="Ollama API Key",
            info="Your Ollama API key.",
            value=None,
            required=False,
            real_time_refresh=True,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Embeddings", name="embeddings", method="build_embeddings"),
    ]

    @property
    def headers(self) -> dict[str, str] | None:
        """Get the headers for the Ollama API."""
        if self.api_key and self.api_key.strip():
            return {"Authorization": f"Bearer {self.api_key}"}
        return None

    def build_embeddings(self) -> Embeddings:
        transformed_base_url = transform_localhost_url(self.base_url)

        # Strip /v1 suffix if present
        if transformed_base_url and transformed_base_url.rstrip("/").endswith("/v1"):
            transformed_base_url = transformed_base_url.rstrip("/").removesuffix("/v1")
            logger.warning(
                "Detected '/v1' suffix in base URL. The Ollama component uses the native Ollama API, "
                "not the OpenAI-compatible API. The '/v1' suffix has been automatically removed. "
                "If you want to use the OpenAI-compatible API, please use the OpenAI component instead. "
                "Learn more at https://docs.ollama.com/openai#openai-compatibility"
            )

        llm_params = {
            "model": self.model_name,
            "base_url": transformed_base_url,
        }

        if self.headers:
            llm_params["client_kwargs"] = {"headers": self.headers}

        try:
            output = OllamaEmbeddings(**llm_params)
        except Exception as e:
            msg = (
                "Unable to connect to the Ollama API. "
                "Please verify the base URL, ensure the relevant Ollama model is pulled, and try again."
            )
            raise ValueError(msg) from e
        return output

    async def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None):
        if field_name in {"base_url", "model_name"} and not await self.is_valid_ollama_url(self.base_url):
            msg = "Ollama is not running on the provided base URL. Please start Ollama and try again."
            raise ValueError(msg)
        if field_name in {"model_name", "base_url"}:
            # Use field_value if base_url is being updated, otherwise use self.base_url
            base_url_to_check = field_value if field_name == "base_url" else self.base_url
            # Fallback to self.base_url if field_value is None or empty
            if not base_url_to_check and field_name == "base_url":
                base_url_to_check = self.base_url
            logger.warning(f"Fetching Ollama models from updated URL: {base_url_to_check}")

            if base_url_to_check and await self.is_valid_ollama_url(base_url_to_check):
                build_config["model_name"]["options"] = await self.get_model(base_url_to_check)
            else:
                build_config["model_name"]["options"] = []

        return build_config

    async def get_model(self, base_url_value: str) -> list[str]:
        """Get the model names from Ollama."""
        try:
            # Strip /v1 suffix if present, as Ollama API endpoints are at root level
            base_url = base_url_value.rstrip("/").removesuffix("/v1")
            if not base_url.endswith("/"):
                base_url = base_url + "/"
            base_url = transform_localhost_url(base_url)

            # Ollama REST API to return models
            tags_url = urljoin(base_url, "api/tags")

            # Ollama REST API to return model capabilities
            show_url = urljoin(base_url, "api/show")

            async with httpx.AsyncClient() as client:
                headers = self.headers
                # Fetch available models
                tags_response = await client.get(url=tags_url, headers=headers)
                tags_response.raise_for_status()
                models = tags_response.json()
                if asyncio.iscoroutine(models):
                    models = await models
                await logger.adebug(f"Available models: {models}")

                # Filter models that are embedding models
                model_ids = []
                for model in models[self.JSON_MODELS_KEY]:
                    model_name = model[self.JSON_NAME_KEY]
                    await logger.adebug(f"Checking model: {model_name}")

                    payload = {"model": model_name}
                    show_response = await client.post(url=show_url, json=payload, headers=headers)
                    show_response.raise_for_status()
                    json_data = show_response.json()
                    if asyncio.iscoroutine(json_data):
                        json_data = await json_data

                    capabilities = json_data.get(self.JSON_CAPABILITIES_KEY, [])
                    await logger.adebug(f"Model: {model_name}, Capabilities: {capabilities}")

                    if self.EMBEDDING_CAPABILITY in capabilities:
                        model_ids.append(model_name)

        except (httpx.RequestError, ValueError) as e:
            msg = "Could not get model names from Ollama."
            raise ValueError(msg) from e

        return model_ids

    async def is_valid_ollama_url(self, url: str) -> bool:
        try:
            async with httpx.AsyncClient() as client:
                url = transform_localhost_url(url)
                if not url:
                    return False
                # Strip /v1 suffix if present, as Ollama API endpoints are at root level
                url = url.rstrip("/").removesuffix("/v1")
                if not url.endswith("/"):
                    url = url + "/"
                return (
                    await client.get(url=urljoin(url, "api/tags"), headers=self.headers)
                ).status_code == HTTP_STATUS_OK
        except httpx.RequestError:
            return False

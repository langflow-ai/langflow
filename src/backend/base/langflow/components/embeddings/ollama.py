from typing import Any
from urllib.parse import urljoin

import httpx
from langchain_ollama import OllamaEmbeddings

from langflow.base.models.model import LCModelComponent
from langflow.base.models.ollama_constants import OLLAMA_EMBEDDING_MODELS, URL_LIST
from langflow.field_typing import Embeddings
from langflow.io import DropdownInput, MessageTextInput, Output

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
        try:
            output = OllamaEmbeddings(model=self.model_name, base_url=self.base_url)
        except Exception as e:
            msg = (
                "Unable to connect to the Ollama API. ",
                "Please verify the base URL, ensure the relevant Ollama model is pulled, and try again.",
            )
            raise ValueError(msg) from e
        return output

    async def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None):
        if field_name in {"base_url", "model_name"} and not await self.is_valid_ollama_url(field_value):
            # Check if any URL in the list is valid
            valid_url = ""
            for url in URL_LIST:
                if await self.is_valid_ollama_url(url):
                    valid_url = url
                    break
            build_config["base_url"]["value"] = valid_url
        if field_name in {"model_name", "base_url", "tool_model_enabled"}:
            if await self.is_valid_ollama_url(self.base_url):
                build_config["model_name"]["options"] = await self.get_model(self.base_url)
            elif await self.is_valid_ollama_url(build_config["base_url"].get("value", "")):
                build_config["model_name"]["options"] = await self.get_model(build_config["base_url"].get("value", ""))
            else:
                build_config["model_name"]["options"] = []

        return build_config

    async def get_model(self, base_url_value: str) -> list[str]:
        """Get the model names from Ollama."""
        model_ids = []
        try:
            url = urljoin(base_url_value, "/api/tags")
            async with httpx.AsyncClient() as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()

            model_ids = [model["name"] for model in data.get("models", [])]
            # this to ensure that not embedding models are included.
            # not even the base models since models can have 1b 2b etc
            # handles cases when embeddings models have tags like :latest - etc.
            model_ids = [
                model
                for model in model_ids
                if any(model.startswith(f"{embedding_model}") for embedding_model in OLLAMA_EMBEDDING_MODELS)
            ]

        except (ImportError, ValueError, httpx.RequestError) as e:
            msg = "Could not get model names from Ollama."
            raise ValueError(msg) from e

        return model_ids

    async def is_valid_ollama_url(self, url: str) -> bool:
        try:
            async with httpx.AsyncClient() as client:
                return (await client.get(f"{url}/api/tags")).status_code == HTTP_STATUS_OK
        except httpx.RequestError:
            return False

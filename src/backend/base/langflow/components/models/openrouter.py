from collections import defaultdict
from typing import Any

import httpx
from langchain_openai import ChatOpenAI
from pydantic.v1 import SecretStr

from langflow.base.models.model import LCModelComponent
from langflow.field_typing import LanguageModel
from langflow.field_typing.range_spec import RangeSpec
from langflow.inputs import (
    BoolInput,
    DropdownInput,
    IntInput,
    SecretStrInput,
    SliderInput,
    StrInput,
)


class OpenRouterComponent(LCModelComponent):
    """OpenRouter API component for language models."""

    display_name = "OpenRouter"
    description = (
        "OpenRouter provides unified access to multiple AI models "
        "from different providers through a single API."
    )
    icon = "OpenRouter"

    inputs = [
        *LCModelComponent._base_inputs,
        SecretStrInput(
            name="api_key",
            display_name="OpenRouter API Key",
            required=True,
            info="Your OpenRouter API key"
        ),
        StrInput(
            name="site_url",
            display_name="Site URL",
            info="Your site URL for OpenRouter rankings",
            advanced=True,
        ),
        StrInput(
            name="app_name",
            display_name="App Name",
            info="Your app name for OpenRouter rankings",
            advanced=True,
        ),
        DropdownInput(
            name="provider",
            display_name="Provider",
            info="The AI model provider",
            options=["Loading providers..."],
            value="Loading providers...",
            real_time_refresh=True,
        ),
        DropdownInput(
            name="model_name",
            display_name="Model",
            info="The model to use for chat completion",
            options=["Select a provider first"],
            value="Select a provider first",
            real_time_refresh=True,
        ),
        SliderInput(
            name="temperature",
            display_name="Temperature",
            value=0.7,
            range_spec=RangeSpec(min=0, max=2, step=0.01)
        ),
        IntInput(
            name="max_tokens",
            display_name="Max Tokens",
            info="Maximum number of tokens to generate",
            advanced=True,
        ),
    ]

    def fetch_models(self) -> dict[str, list]:
        """Fetch available models from OpenRouter API and organize them by provider."""
        url = "https://openrouter.ai/api/v1/models"

        try:
            with httpx.Client() as client:
                response = client.get(url)
                response.raise_for_status()

                models_data = response.json().get("data", [])
                provider_models = defaultdict(list)

                for model in models_data:
                    model_id = model.get("id", "")
                    if "/" in model_id:
                        provider = model_id.split("/")[0].title()
                        provider_models[provider].append({
                            "id": model_id,
                            "name": model.get("name", ""),
                            "description": model.get("description", ""),
                            "context_length": model.get("context_length", 0)
                        })

                return dict(provider_models)

        except httpx.HTTPError as e:
            self.log(f"Error fetching models: {e!s}")
            return {"Error": [{"id": "error", "name": f"Error fetching models: {e!s}"}]}

    def build_model(self) -> LanguageModel:
        """Build and return the OpenRouter language model."""
        if not self.model_name or self.model_name == "Select a provider first":
            raise ValueError("Please select a model")

        if not self.api_key:
            raise ValueError("API key is required")

        api_key = SecretStr(self.api_key).get_secret_value()

        # Build base configuration
        kwargs: dict[str, Any] = {
            "model": self.model_name,
            "openai_api_key": api_key,
            "openai_api_base": "https://openrouter.ai/api/v1",
            "temperature": self.temperature if self.temperature is not None else 0.7,
        }

        # Add optional parameters
        if self.max_tokens:
            kwargs["max_tokens"] = self.max_tokens

        headers = {}
        if self.site_url:
            headers["HTTP-Referer"] = self.site_url
        if self.app_name:
            headers["X-Title"] = self.app_name

        if headers:
            kwargs["default_headers"] = headers

        try:
            chat_model = ChatOpenAI(**kwargs)
            # Test if the model can be initialized
            if not chat_model:
                raise ValueError("Failed to initialize ChatOpenAI model")
            return chat_model
        except Exception as e:
            self.log(f"Error building model: {str(e)}")
            raise ValueError(f"Failed to build model: {str(e)}")

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None) -> dict:
        """Update build configuration based on field updates."""
        try:
            if field_name is None or field_name == "provider":
                provider_models = self.fetch_models()
                build_config["provider"]["options"] = sorted(provider_models.keys())
                if build_config["provider"]["value"] not in provider_models:
                    build_config["provider"]["value"] = build_config["provider"]["options"][0]

            if field_name == "provider" and field_value in self.fetch_models():
                provider_models = self.fetch_models()
                models = provider_models[field_value]

                build_config["model_name"]["options"] = [model["id"] for model in models]
                if models:
                    build_config["model_name"]["value"] = models[0]["id"]

                tooltips = {
                    model["id"]: (
                        f"{model['name']}\n"
                        f"Context Length: {model['context_length']}\n"
                        f"{model['description']}"
                    ) for model in models
                }
                build_config["model_name"]["tooltips"] = tooltips

        except httpx.HTTPError as e:
            self.log(f"Error updating build config: {e!s}")
            build_config["provider"]["options"] = ["Error loading providers"]
            build_config["provider"]["value"] = "Error loading providers"
            build_config["model_name"]["options"] = ["Error loading models"]
            build_config["model_name"]["value"] = "Error loading models"

        return build_config

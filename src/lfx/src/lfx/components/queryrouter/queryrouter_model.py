import contextlib
from typing import Any

import httpx
from langchain_openai import ChatOpenAI
from pydantic.v1 import SecretStr

from lfx.base.models.model import LCModelComponent
from lfx.field_typing import LanguageModel
from lfx.inputs.inputs import (
    BoolInput,
    DictInput,
    DropdownInput,
    IntInput,
    SecretStrInput,
    SliderInput,
)
from lfx.log.logger import logger


class QueryRouterModelComponent(LCModelComponent):
    display_name = "QueryRouter"
    description = "Generates text using QueryRouter API - OpenAI-compatible interface."
    icon = "Globe"
    name = "QueryRouterModel"
    API_BASE = "https://api.queryrouter.ru/v1"

    inputs = [
        *LCModelComponent.get_base_inputs(),
        IntInput(
            name="max_tokens",
            display_name="Max Tokens",
            advanced=True,
            info="The maximum number of tokens to generate. Set to 0 for unlimited tokens.",
        ),
        DictInput(
            name="model_kwargs",
            display_name="Model Kwargs",
            advanced=True,
            info="Additional keyword arguments to pass to the model.",
        ),
        BoolInput(
            name="json_mode",
            display_name="JSON Mode",
            advanced=True,
            info="If True, it will output JSON regardless of passing a schema.",
        ),
        DropdownInput(
            name="model_name",
            display_name="Model Name",
            advanced=False,
            options=[],  # Will be populated dynamically from /v1/models
            value="gpt-4o",
            combobox=True,
            real_time_refresh=True,
            info="Model to use for generation. Models are fetched from QueryRouter API.",
        ),
        SecretStrInput(
            name="api_key",
            display_name="QueryRouter API Key",
            info="Your QueryRouter API key for authentication.",
            advanced=False,
            value="QUERYROUTER_API_KEY",
            required=True,
        ),
        SliderInput(
            name="temperature",
            display_name="Temperature",
            value=0.1,
            range_spec={"min": 0, "max": 1, "step": 0.01},
            show=True,
        ),
        IntInput(
            name="seed",
            display_name="Seed",
            info="The seed controls the reproducibility of the job.",
            advanced=True,
            value=1,
        ),
        IntInput(
            name="max_retries",
            display_name="Max Retries",
            info="The maximum number of retries to make when generating.",
            advanced=True,
            value=5,
        ),
        IntInput(
            name="timeout",
            display_name="Timeout",
            info="The timeout for requests to QueryRouter API.",
            advanced=True,
            value=700,
        ),
    ]

    def fetch_models(self) -> list[dict]:
        """Fetch available models from QueryRouter's OpenAI-compatible /models endpoint.

        Returns a list of dicts with keys: id, name, context.
        """
        models_url = f"{self.API_BASE}/models"

        # Prepare Authorization header if api_key provided
        headers: dict[str, str] = {}
        api_key_value: str | None = None
        if getattr(self, "api_key", None):
            if isinstance(self.api_key, SecretStr):
                api_key_value = self.api_key.get_secret_value()
            else:
                api_key_value = str(self.api_key)
        if api_key_value:
            headers["Authorization"] = f"Bearer {api_key_value}"

        try:
            response = httpx.get(models_url, headers=headers, timeout=10.0)
            response.raise_for_status()
            data = response.json() or {}
            models = data.get("data", [])
            # Normalize and sort by display name
            normalized = [
                {
                    "id": m.get("id"),
                    "name": m.get("display_name") or m.get("name") or m.get("id"),
                    "context": m.get("context_length", "N/A"),
                }
                for m in models
                if m.get("id")
            ]
            return sorted(normalized, key=lambda x: x["name"])
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            logger.error(f"Error fetching QueryRouter models: {e}")
            return []

    def update_build_config(self, build_config: dict) -> dict:
        """Populate model_name dropdown with models fetched from QueryRouter."""
        models = self.fetch_models()
        if models:
            build_config["model_name"]["options"] = [m["id"] for m in models]
            build_config["model_name"]["tooltips"] = {m["id"]: f"{m['name']} ({m['context']} tokens)" for m in models}
            # Preserve current value if still valid; otherwise set default
            current = build_config["model_name"].get("value")
            if not current or current not in build_config["model_name"]["options"]:
                build_config["model_name"]["value"] = models[0]["id"]
        else:
            build_config["model_name"]["options"] = ["Failed to load models"]
            build_config["model_name"]["value"] = "Failed to load models"
        return build_config

    def build_model(self) -> LanguageModel:  # type: ignore[type-var]
        logger.debug(f"Executing request with model: {self.model_name}")
        # Handle api_key - it can be string or SecretStr
        api_key_value = None
        if self.api_key:
            if isinstance(self.api_key, SecretStr):
                api_key_value = self.api_key.get_secret_value()
            else:
                api_key_value = str(self.api_key)

        # Build the model
        # Assemble kwargs in a safe, OpenRouter-like way
        kwargs: dict[str, Any] = {
            "model": self.model_name or "gpt-4o",
            "openai_api_key": api_key_value,
            "openai_api_base": self.API_BASE,
            "temperature": self.temperature if self.temperature is not None else 0.1,
            "seed": self.seed,
            "max_retries": self.max_retries,
            "request_timeout": self.timeout,
            "model_kwargs": self.model_kwargs or {},
        }

        # Only pass max_tokens if set to a valid integer
        if getattr(self, "max_tokens", None) not in (None, "", 0):
            with contextlib.suppress(TypeError, ValueError):
                kwargs["max_tokens"] = int(self.max_tokens)

        model = ChatOpenAI(**kwargs)

        if self.json_mode:
            model = model.bind(response_format={"type": "json_object"})

        return model

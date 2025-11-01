import httpx
from langchain_openai import ChatOpenAI
from pydantic.v1 import SecretStr

from lfx.base.models.model import LCModelComponent
from lfx.field_typing import LanguageModel
from lfx.field_typing.range_spec import RangeSpec
from lfx.inputs.inputs import DropdownInput, IntInput, SecretStrInput, SliderInput


class QueryRouterModelComponent(LCModelComponent):
    """QueryRouter API component for language models."""

    display_name = "QueryRouter"
    description = "QueryRouter provides unified access to multiple AI models through an OpenAI-compatible API."
    icon = "Globe"
    name = "QueryRouterModel"

    inputs = [
        *LCModelComponent.get_base_inputs(),
        SecretStrInput(
            name="api_key",
            display_name="QueryRouter API Key",
            required=True,
            value="QUERYROUTER_API_KEY",
        ),
        DropdownInput(
            name="model_name",
            display_name="Model",
            options=[],
            value="",
            refresh_button=True,
            real_time_refresh=True,
            required=True,
        ),
        SliderInput(
            name="temperature",
            display_name="Temperature",
            value=0.7,
            range_spec=RangeSpec(min=0, max=2, step=0.01),
            advanced=True,
        ),
        IntInput(
            name="max_tokens",
            display_name="Max Tokens",
            advanced=True,
        ),
    ]

    def fetch_models(self) -> list[dict]:
        """Fetch available models from QueryRouter."""
        try:
            # Prepare headers with API key if available
            headers = {}
            if self.api_key:
                if isinstance(self.api_key, SecretStr):
                    api_key_value = SecretStr(self.api_key).get_secret_value()
                else:
                    api_key_value = str(self.api_key)
                headers["Authorization"] = f"Bearer {api_key_value}"

            response = httpx.get("https://api.queryrouter.ru/v1/models", headers=headers, timeout=10.0)
            response.raise_for_status()
            models = response.json().get("data", [])
            return sorted(
                [
                    {
                        "id": m["id"],
                        "name": m.get("display_name") or m.get("name", m["id"]),
                        "context": m.get("context_length", 0),
                    }
                    for m in models
                    if m.get("id")
                ],
                key=lambda x: x["name"],
            )
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            self.log(f"Error fetching models: {e}")
            return []

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None) -> dict:  # noqa: ARG002
        """Update model options."""
        models = self.fetch_models()
        if models:
            build_config["model_name"]["options"] = [m["id"] for m in models]
            build_config["model_name"]["tooltips"] = {m["id"]: f"{m['name']} ({m['context']:,} tokens)" for m in models}
        else:
            build_config["model_name"]["options"] = ["Failed to load models"]
        return build_config

    def build_model(self) -> LanguageModel:
        """Build the QueryRouter model."""
        if not self.api_key:
            msg = "API key is required"
            raise ValueError(msg)
        if not self.model_name or self.model_name == "Loading...":
            msg = "Please select a model"
            raise ValueError(msg)

        kwargs = {
            "model": self.model_name,
            "openai_api_key": SecretStr(self.api_key).get_secret_value(),
            "openai_api_base": "https://api.queryrouter.ru/v1",
            "temperature": self.temperature if self.temperature is not None else 0.7,
        }

        if self.max_tokens:
            kwargs["max_tokens"] = int(self.max_tokens)

        return ChatOpenAI(**kwargs)

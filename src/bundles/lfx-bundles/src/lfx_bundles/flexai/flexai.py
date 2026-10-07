import httpx
from langchain_openai import ChatOpenAI
from lfx.base.models.model import LCModelComponent
from lfx.field_typing import LanguageModel
from lfx.field_typing.range_spec import RangeSpec
from lfx.inputs.inputs import DropdownInput, IntInput, SecretStrInput, SliderInput
from pydantic.v1 import SecretStr

FLEXAI_API_BASE = "https://api.flex.ai/v1"
FLEXAI_DEFAULT_MODEL = "DeepSeek-V4-Flash-0731"


class FlexAIModelComponent(LCModelComponent):
    """FlexAI API component for language models."""

    display_name = "FlexAI"
    description = "Generate text using open models served by FlexAI's OpenAI-compatible inference API."
    icon = "FlexAI"

    inputs = [
        *LCModelComponent.get_base_inputs(),
        SecretStrInput(
            name="api_key",
            display_name="FlexAI API Key",
            info="Your FlexAI API key. Create one at https://platform.flex.ai.",
            required=True,
            real_time_refresh=True,
        ),
        DropdownInput(
            name="model_name",
            display_name="Model",
            info="Add your API key to load the chat models currently served by FlexAI.",
            options=[FLEXAI_DEFAULT_MODEL],
            value=FLEXAI_DEFAULT_MODEL,
            refresh_button=True,
            real_time_refresh=True,
            combobox=True,
            required=True,
        ),
        SliderInput(
            name="temperature",
            display_name="Temperature",
            value=0.7,
            range_spec=RangeSpec(min=0, max=2, step=0.01),
            advanced=True,
        ),
        IntInput(name="max_tokens", display_name="Max Tokens", advanced=True),
    ]

    def fetch_models(self) -> list[dict]:
        """Fetch the chat models currently served by FlexAI."""
        if not self.api_key:
            return []
        headers = {"Authorization": f"Bearer {SecretStr(self.api_key).get_secret_value()}"}
        try:
            response = httpx.get(f"{FLEXAI_API_BASE}/models", headers=headers, timeout=10.0)
            response.raise_for_status()
            models = response.json().get("data", [])
            return sorted(
                [
                    {
                        "id": m["id"],
                        "name": m.get("name", m["id"]),
                        "context": m.get("context_length") or 0,
                    }
                    for m in models
                    # The catalog also lists embedding, speech and image models; keep chat models only.
                    if m.get("id") and "chat" in m.get("supports", ["chat"])
                ],
                key=lambda x: x["name"],
            )
        except (httpx.RequestError, httpx.HTTPStatusError, ValueError) as e:
            self.log(f"Error fetching models: {e}")
            return []

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None) -> dict:  # noqa: ARG002
        """Update model options."""
        models = self.fetch_models()
        if models:
            ids = [m["id"] for m in models]
            build_config["model_name"]["options"] = ids
            build_config["model_name"]["tooltips"] = {m["id"]: f"{m['name']} ({m['context']:,} tokens)" for m in models}
            if build_config["model_name"].get("value") not in ids:
                build_config["model_name"]["value"] = FLEXAI_DEFAULT_MODEL if FLEXAI_DEFAULT_MODEL in ids else ids[0]
        return build_config

    def build_model(self) -> LanguageModel:
        """Build the FlexAI model."""
        if not self.api_key:
            msg = "API key is required"
            raise ValueError(msg)
        if not self.model_name:
            msg = "Please select a model"
            raise ValueError(msg)

        kwargs = {
            "model": self.model_name,
            "openai_api_key": SecretStr(self.api_key).get_secret_value(),
            "openai_api_base": FLEXAI_API_BASE,
            "temperature": self.temperature if self.temperature is not None else 0.7,
            "streaming": self.stream,
        }

        if self.max_tokens:
            kwargs["max_tokens"] = int(self.max_tokens)

        return ChatOpenAI(**kwargs)
